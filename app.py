"""
Fake Account Detector — Flask Web Interface
Run with: python app.py
Then open: http://127.0.0.1:5000
"""

import sys
import os

# Add project root to path so we can import src/predict.py
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, render_template, request, redirect, url_for
from src.predict import predict
import pandas as pd

app = Flask(__name__)

# ── Load dataset once at startup ───────────────────────────────────────────

DATA_PATH = os.path.join(PROJECT_ROOT, "data")

def load_all_accounts():
    groups = {
        "genuine_accounts":       0,
        "social_spambots_1":      1,
        "social_spambots_2":      1,
        "social_spambots_3":      1,
        "traditional_spambots_1": 1,
        "fake_followers":         1,
    }
    frames = []
    for folder, label in groups.items():
        path = os.path.join(DATA_PATH, folder, "users.csv")
        if os.path.exists(path):
            df = pd.read_csv(path)
            df["true_label"] = label
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    combined["screen_name_lower"] = combined["screen_name"].str.lower().fillna("")
    return combined

print("Loading dataset...")
accounts_df = load_all_accounts()
print(f"{len(accounts_df):,} accounts loaded.")


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyse", methods=["POST"])
def analyse():
    screen_name = request.form.get("screen_name", "").strip().lstrip("@")

    if not screen_name:
        return render_template("index.html", error="Please enter a screen name.")

    # Try dataset lookup first
    match = accounts_df[accounts_df["screen_name_lower"] == screen_name.lower()] \
        if not accounts_df.empty else pd.DataFrame()

    if not match.empty:
        account    = match.iloc[0].to_dict()
        true_label = int(account.get("true_label", -1))
        result     = predict(account)
        result["true_label"]  = true_label
        result["input_source"] = "dataset"
        return render_template("result.html", result=result)

    # Not in dataset — check if manual fields were submitted
    followers  = request.form.get("followers_count",  "").strip()
    if followers:
        # Manual input was provided
        def safe_int(key):
            try:
                return max(0, int(request.form.get(key, 0) or 0))
            except ValueError:
                return 0

        account = {
            "screen_name":      screen_name,
            "name":             screen_name,
            "followers_count":  safe_int("followers_count"),
            "friends_count":    safe_int("friends_count"),
            "statuses_count":   safe_int("statuses_count"),
            "favourites_count": safe_int("favourites_count"),
            "listed_count":     safe_int("listed_count"),
            "description":      "yes" if request.form.get("has_description") else "",
            "url":              "yes" if request.form.get("has_url")         else None,
            "location":         "yes" if request.form.get("has_location")    else "",
            "created_at":       request.form.get("created_at", "").strip() or None,
        }
        result = predict(account)
        result["true_label"]   = -1
        result["input_source"] = "manual"
        return render_template("result.html", result=result)

    # Not in dataset and no manual input — ask for manual stats
    return render_template("index.html",
                           not_found=screen_name,
                           screen_name=screen_name)


if __name__ == "__main__":
    app.run(debug=True)


