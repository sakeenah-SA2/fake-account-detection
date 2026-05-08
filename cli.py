"""
Fake Account Detector — Command Line Interface
Usage:
    python cli.py                        # interactive mode
    python cli.py --name some_username   # direct lookup
"""

import sys
import os
import argparse
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.predict import predict

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data")


# ── data loading ──────────────────────────────────────────────────────────────

def load_all_accounts() -> pd.DataFrame:
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
    combined = pd.concat(frames, ignore_index=True)
    combined["screen_name_lower"] = combined["screen_name"].str.lower().fillna("")
    return combined


# ── display ───────────────────────────────────────────────────────────────────

def display_result(result: dict, true_label: int = None):
    verdict     = result["verdict"]
    probability = result["bot_probability"]
    confidence  = result["confidence"]
    pct         = f"{probability * 100:.1f}%"

    print()
    print("━" * 52)
    print(f"  Account   : @{result['screen_name']}  ({result['name']})")
    print(f"  Verdict   : {verdict}  ({confidence} confidence)")
    print(f"  Bot score : {pct}")

    if true_label is not None:
        actual = "FAKE" if true_label == 1 else "REAL"
        match  = "✓ Correct" if actual == verdict else "✗ Wrong"
        print(f"  Actual    : {actual}  {match}")
    else:
        print(f"  Actual    : Unknown (not in dataset)")

    print("━" * 52)

    filled = int(probability * 30)
    bar    = "█" * filled + "░" * (30 - filled)
    print(f"  Real ◄ [{bar}] ► Fake")
    print()

    print("  Key signals:")
    for label_text, value in result["top_signals"]:
        print(f"    {label_text:<30} {value}")
    print("━" * 52)
    print()


# ── manual input ──────────────────────────────────────────────────────────────

def prompt_int(question: str, default: int = 0) -> int:
    """Ask the user to type a whole number. Uses default if they just press Enter."""
    while True:
        raw = input(f"  {question} [default {default}]: ").strip()
        if raw == "":
            return default
        try:
            return int(raw)
        except ValueError:
            print("  Please enter a whole number.")


def prompt_yes_no(question: str, default: bool = False) -> bool:
    """Ask the user a yes/no question."""
    hint   = "Y/n" if default else "y/N"
    raw    = input(f"  {question} [{hint}]: ").strip().lower()
    if raw == "":
        return default
    return raw in ("y", "yes")


def manual_input_mode(screen_name: str) -> dict:
    """
    Ask the user to type in the account's stats manually.
    They can look these up on Twitter/X in a browser.
    Returns a raw account dict compatible with predict().
    """
    print()
    print(f"  '@{screen_name}' is not in the dataset.")
    print("  You can look up these numbers on Twitter/X and enter them manually.")
    print("  Just press Enter to accept the default (0) if you're unsure.\n")

    followers  = prompt_int("Followers count")
    friends    = prompt_int("Following count")
    statuses   = prompt_int("Total tweets (statuses)")
    favourites = prompt_int("Total likes given")
    listed     = prompt_int("Listed count (times added to lists)")
    has_desc   = prompt_yes_no("Does the account have a bio / description?")
    has_url    = prompt_yes_no("Does the account have a website URL in profile?")
    has_loc    = prompt_yes_no("Does the account have a location set?")
    created_at = input("  Account creation date (e.g. 2021-03-15), or press Enter to skip: ").strip()

    return {
        "screen_name":      screen_name,
        "name":             screen_name,
        "followers_count":  followers,
        "friends_count":    friends,
        "statuses_count":   statuses,
        "favourites_count": favourites,
        "listed_count":     listed,
        "description":      "yes" if has_desc else "",
        "url":              "yes" if has_url  else None,
        "location":         "yes" if has_loc  else "",
        "created_at":       created_at if created_at else None,
    }


# ── core lookup logic ─────────────────────────────────────────────────────────

def lookup_and_predict(screen_name: str, accounts_df: pd.DataFrame):
    """
    Try the dataset first.
    If not found, fall back to asking the user to enter stats manually.
    """
    clean_name = screen_name.lower().lstrip("@")
    match      = accounts_df[accounts_df["screen_name_lower"] == clean_name]

    if not match.empty:
        # ── found in dataset ──────────────────────────────────────────────────
        account    = match.iloc[0].to_dict()
        true_label = int(account.get("true_label", -1))
        print(f"\n  Found @{screen_name} in dataset.")
        result = predict(account)
        display_result(result, true_label)

    else:
        # ── not in dataset — offer manual fallback ────────────────────────────
        account = manual_input_mode(screen_name)
        result  = predict(account)
        display_result(result, true_label=None)  # no ground truth available


# ── interactive loop ──────────────────────────────────────────────────────────

def interactive_mode(accounts_df: pd.DataFrame):
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║      Fake Account Detector  v1.0             ║")
    print("║      Type a Twitter screen name to analyse   ║")
    print("║      Type 'quit' to exit                     ║")
    print("╚══════════════════════════════════════════════╝")

    while True:
        print()
        try:
            screen_name = input("  Enter screen name: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Goodbye!")
            break

        if screen_name.lower() in ("quit", "exit", "q"):
            print("  Goodbye!")
            break

        if not screen_name:
            continue

        lookup_and_predict(screen_name, accounts_df)


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fake Twitter account detector")
    parser.add_argument(
        "--name", "-n",
        type=str,
        default=None,
        help="Screen name to analyse (with or without @)"
    )
    args = parser.parse_args()

    print("\n  Loading dataset and model...")
    accounts_df = load_all_accounts()
    print(f"  {len(accounts_df):,} accounts loaded.")

    if args.name:
        lookup_and_predict(args.name, accounts_df)
    else:
        interactive_mode(accounts_df)
# ```
#
# ---
#
# ## What changed
#
# The only meaningful addition is the `manual_input_mode()` function and the updated `lookup_and_predict()` logic. Here's the flow:
# ```
# User types a screen name
#         │
#         ▼
# Found in dataset? ──── YES ──▶ predict immediately, show ground truth
#         │
#         NO
#         │
#         ▼
# Ask user to type in the numbers manually
# (they look them up on Twitter/X in browser)
#         │
#         ▼
# predict from manual input, show result (no ground truth)
# ```
#
# ---
#
# ## How the manual mode works in practice
#
# If you type a name not in the dataset, you'll see something like:
# ```
#   '@elonmusk' is not in the dataset.
#   You can look up these numbers on Twitter/X and enter them manually.
#   Just press Enter to accept the default (0) if you're unsure.
#
#   Followers count [default 0]: 170000000
#   Following count [default 0]: 700
#   Total tweets (statuses) [default 0]: 45000
#   Total likes given [default 0]: 85000
#   Listed count [default 0]: 150000
#   Does the account have a bio? [y/N]: y
#   Does the account have a website URL? [y/N]: y
#   Does the account have a location set? [y/N]: y
#   Account creation date (e.g. 2021-03-15): 2009-06-02