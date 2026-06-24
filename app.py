"""
Fake Account Detector — Flask Web Interface
Run with: python app.py
Then open: http://127.0.0.1:5000
"""

import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, render_template, request, send_from_directory, jsonify
from src.predict import predict
import pandas as pd

app = Flask(__name__)


def load_all_accounts() -> pd.DataFrame:
    lookup_path = os.path.join(PROJECT_ROOT, "data", "accounts_lookup.csv")
    if not os.path.exists(lookup_path):
        print("WARNING: accounts_lookup.csv not found.")
        return pd.DataFrame()
    df = pd.read_csv(lookup_path)
    df["screen_name_lower"] = df["screen_name"].str.lower().fillna("")
    print(f"Loaded {len(df):,} accounts.")
    return df


print("Loading dataset...")
accounts_df = load_all_accounts()


def _to_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def query_accounts(q="", label="all", page=1, per_page=50):
    """Filter/paginate the lookup dataset. Shared by the page, API and CLI."""
    per_page = max(1, min(_to_int(per_page, 50), 200))
    page     = max(1, _to_int(page, 1))

    if accounts_df.empty:
        return {"total": 0, "page": 1, "per_page": per_page, "pages": 0, "accounts": []}

    mask = pd.Series(True, index=accounts_df.index)
    if label == "real":
        mask &= accounts_df["true_label"] == 0
    elif label == "fake":
        mask &= accounts_df["true_label"] == 1

    q = (q or "").strip().lower()
    if q:
        names = accounts_df["name"].astype(str).str.lower()
        mask &= (
            accounts_df["screen_name_lower"].str.contains(q, na=False, regex=False)
            | names.str.contains(q, na=False, regex=False)
        )

    subset = accounts_df[mask]
    total  = len(subset)
    pages  = (total + per_page - 1) // per_page
    page   = min(page, pages) if pages else 1
    start  = (page - 1) * per_page
    rows   = subset.iloc[start:start + per_page]

    accounts = [
        {
            "screen_name": str(r["screen_name"]),
            "name":        "" if pd.isna(r.get("name")) else str(r["name"]),
            "true_label":  int(r["true_label"]),
        }
        for _, r in rows.iterrows()
    ]
    return {"total": total, "page": page, "per_page": per_page, "pages": pages, "accounts": accounts}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/google805b58db16185516.html")
def google_site_verification():
    """Serve the Google Search Console ownership-verification file."""
    return send_from_directory(PROJECT_ROOT, "google805b58db16185516.html")


@app.route("/privacy")
def privacy():
    """Privacy policy (required for the Chrome Web Store listing)."""
    return render_template("privacy.html")


@app.route("/analyse", methods=["POST"])
def analyse():
    screen_name = request.form.get("screen_name", "").strip().lstrip("@")

    if not screen_name:
        return render_template("index.html", error="Please enter a screen name.")

    if not accounts_df.empty:
        match = accounts_df[accounts_df["screen_name_lower"] == screen_name.lower()]
    else:
        match = pd.DataFrame()

    if not match.empty:
        account    = match.iloc[0].to_dict()
        true_label = int(account.get("true_label", -1))
        result     = predict(account)
        result["true_label"]   = true_label
        result["input_source"] = "dataset"
        return render_template("result.html", result=result)

    followers = request.form.get("followers_count", "").strip()
    if followers:
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
            "url":              "yes" if request.form.get("has_url") else None,
            "location":         "yes" if request.form.get("has_location") else "",
            "created_at":       request.form.get("created_at", "").strip() or None,
        }
        result = predict(account)
        result["true_label"]   = -1
        result["input_source"] = "manual"
        return render_template("result.html", result=result)

    return render_template("index.html", not_found=screen_name, screen_name=screen_name)

@app.route("/accounts")
def accounts_page():
    """Browse the lookup dataset in the browser."""
    q     = request.args.get("q", "")
    label = request.args.get("label", "all")
    data  = query_accounts(q=q, label=label, page=request.args.get("page", 1))
    return render_template("accounts.html", data=data, q=q, label=label)


@app.route("/accounts-json")
def accounts_json():
    """Paginated/searchable list of dataset accounts (used by the CLI)."""
    return jsonify(query_accounts(
        q=request.args.get("q", ""),
        label=request.args.get("label", "all"),
        page=request.args.get("page", 1),
        per_page=request.args.get("per_page", 50),
    ))


@app.route("/lookup-json")
def lookup_json():
    """Look up a screen name in the bundled dataset (used by the standalone CLI).

    Returns the model's verdict plus the dataset's ground-truth label when the
    account is found, or {"found": false} so the client can fall back to manual
    entry.
    """
    name = request.args.get("name", "").strip().lstrip("@").lower()
    if not name:
        return jsonify({"error": "Missing 'name' parameter"}), 400

    if accounts_df.empty:
        return jsonify({"found": False, "screen_name": name})

    match = accounts_df[accounts_df["screen_name_lower"] == name]
    if match.empty:
        return jsonify({"found": False, "screen_name": name})

    account = match.iloc[0].to_dict()
    result = predict(account)
    result["true_label"]   = int(account.get("true_label", -1))
    result["input_source"] = "dataset"
    result["found"]        = True
    result["top_signals"]  = [list(s) for s in result["top_signals"]]
    return jsonify(result)


@app.route("/predict-json", methods=["POST"])
def predict_json():
    """JSON endpoint used by the Chrome extension."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400
    try:
        result = predict(data)
        result["true_label"]   = -1
        result["input_source"] = "extension"
        # Convert top_signals tuples to lists for JSON serialisation
        result["top_signals"] = [list(s) for s in result["top_signals"]]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)