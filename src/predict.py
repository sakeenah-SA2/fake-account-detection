import numpy as np
import pandas as pd
import joblib
import os

# ── paths ──────────────────────────────────────────────────────────────────────
# Build paths relative to this file so the module works from any working directory
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH  = os.path.join(BASE_DIR, "models", "random_forest_model.joblib")
SCALER_PATH = os.path.join(BASE_DIR, "models", "scaler.joblib")
COLS_PATH   = os.path.join(BASE_DIR, "data",   "feature_columns.csv")

# ── load model artifacts once at import time ───────────────────────────────────
# Loading from disk is slow — we do it once when the module is first imported
# rather than on every prediction call
model   = joblib.load(MODEL_PATH)
scaler  = joblib.load(SCALER_PATH)
FEATURE_COLUMNS = pd.read_csv(COLS_PATH).squeeze().tolist()

# ── constants ──────────────────────────────────────────────────────────────────
REFERENCE_DATE = pd.Timestamp("2017-01-01", tz="UTC")

# Columns we apply log scaling to — must match what we did in preprocessing
LOG_COLUMNS = [
    "statuses_count", "followers_count", "friends_count",
    "favourites_count", "listed_count", "follower_friend_ratio",
    "tweet_frequency", "favourites_per_tweet", "listed_per_follower",
    "account_age_days"
]


def engineer_features(account: dict) -> dict:
    """
    Takes a raw account dictionary (as it appears in the dataset)
    and returns a dictionary of engineered features ready for the model.

    This mirrors exactly what we did in 02_feature_engineering.ipynb
    so predictions are consistent with how the model was trained.
    """
    # ── account age ───────────────────────────────────────────────────────────
    created_at = pd.to_datetime(account.get("created_at"), errors="coerce", utc=True)
    if pd.isnull(created_at):
        account_age_days = 1433.0  # fallback: dataset median
    else:
        account_age_days = max((REFERENCE_DATE - created_at).days, 0)

    statuses   = float(account.get("statuses_count",   0) or 0)
    followers  = float(account.get("followers_count",  0) or 0)
    friends    = float(account.get("friends_count",    0) or 0)
    favourites = float(account.get("favourites_count", 0) or 0)
    listed     = float(account.get("listed_count",     0) or 0)

    # ── engineered ratios ─────────────────────────────────────────────────────
    follower_friend_ratio = followers / (friends + 1)
    tweet_frequency       = statuses  / (account_age_days + 1)
    favourites_per_tweet  = favourites / (statuses + 1)
    listed_per_follower   = listed     / (followers + 1)

    # ── binary flags ──────────────────────────────────────────────────────────
    has_description = int(len(str(account.get("description") or "").strip()) > 0)
    has_url         = int(account.get("url") is not None and
                          str(account.get("url")).strip() not in ("", "nan"))
    has_location    = int(len(str(account.get("location") or "").strip()) > 0)

    return {
        "statuses_count":       statuses,
        "followers_count":      followers,
        "friends_count":        friends,
        "favourites_count":     favourites,
        "listed_count":         listed,
        "follower_friend_ratio": follower_friend_ratio,
        "tweet_frequency":      tweet_frequency,
        "favourites_per_tweet": favourites_per_tweet,
        "listed_per_follower":  listed_per_follower,
        "has_description":      has_description,
        "has_url":              has_url,
        "has_location":         has_location,
        "account_age_days":     account_age_days,
    }


def predict(account: dict) -> dict:
    """
    Takes a raw account dictionary and returns a prediction result.

    Parameters
    ----------
    account : dict
        Raw account data — keys match the dataset column names.

    Returns
    -------
    dict with keys:
        screen_name   : str
        verdict       : "FAKE" or "REAL"
        bot_probability : float (0.0 – 1.0)
        confidence    : "High" / "Medium" / "Low"
        top_signals   : list of (feature_name, value, direction) tuples
    """
    # Step 1 — engineer features from raw account data
    features = engineer_features(account)

    # Step 2 — build a single-row DataFrame in the right column order
    row = pd.DataFrame([features])[FEATURE_COLUMNS]

    # Step 3 — apply log scaling to the same columns as during training
    for col in LOG_COLUMNS:
        if col in row.columns:
            row[col] = np.log1p(row[col])

    # Step 4 — apply the saved StandardScaler
    row_scaled = scaler.transform(row)

    # Step 5 — get probability from model
    bot_prob = model.predict_proba(row_scaled)[0][1]

    # Step 6 — derive verdict and confidence
    verdict = "FAKE" if bot_prob >= 0.5 else "REAL"

    if bot_prob >= 0.85 or bot_prob <= 0.15:
        confidence = "High"
    elif bot_prob >= 0.65 or bot_prob <= 0.35:
        confidence = "Medium"
    else:
        confidence = "Low"

    # Step 7 — build human-readable top signals for display
    # These are the raw (pre-scaling) values with a note on what they mean
    raw = engineer_features(account)
    top_signals = [
        ("Favourites (likes) given",   int(account.get("favourites_count", 0) or 0)),
        ("Tweets per day",             round(raw["tweet_frequency"], 2)),
        ("Follower / following ratio", round(raw["follower_friend_ratio"], 2)),
        ("Total tweets",               int(account.get("statuses_count", 0) or 0)),
        ("Has bio",                    "Yes" if raw["has_description"] else "No"),
        ("Has location",               "Yes" if raw["has_location"] else "No"),
        ("Has website URL",            "Yes" if raw["has_url"] else "No"),
    ]

    return {
        "screen_name":    account.get("screen_name", "unknown"),
        "name":           account.get("name", ""),
        "verdict":        verdict,
        "bot_probability": round(bot_prob, 4),
        "confidence":     confidence,
        "top_signals":    top_signals,
    }