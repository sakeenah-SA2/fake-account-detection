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

def load_all_accounts() -> pd.DataFrame:
    """Load accounts from the pre-built lookup CSV."""
    lookup_path = os.path.join(BASE_DIR, "data", "accounts_lookup.csv")
    if not os.path.exists(lookup_path):
        print("WARNING: accounts_lookup.csv not found — dataset lookup disabled.")
        return pd.DataFrame()
    df = pd.read_csv(lookup_path)
    df["screen_name_lower"] = df["screen_name"].str.lower().fillna("")
    print(f"Loaded {len(df):,} accounts from accounts_lookup.csv")
    return df
   

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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)


