#!/usr/bin/env python3
"""
BotWatch — Fake Account Detector (standalone CLI)

Checks whether a Twitter/X account is likely fake/bot or real, using the
hosted BotWatch model.

No third-party packages and no local model files are required — predictions
are computed by the hosted API, so this single file (or the bundled .exe)
is all an end user needs.

Usage:
    botwatch                          # interactive mode
    botwatch --name elonmusk          # analyse one account
    botwatch -n elonmusk --api URL    # point at a different server
"""

import sys
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse

DEFAULT_API = "https://botwatch-6qpn.onrender.com"
TIMEOUT = 90  # Render's free tier can take ~30-60s to wake from sleep
VERSION = "1.0"

# Print Unicode box-drawing characters on Windows consoles (cp1252).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


# ── API calls (standard library only) ──────────────────────────────────────────

class ApiError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def _request(url: str, payload: dict = None) -> dict:
    """GET if payload is None, else POST JSON. Returns the parsed JSON body."""
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # The API returns JSON errors with a useful message where possible.
        try:
            body = json.loads(e.read().decode("utf-8"))
            msg = body.get("error", f"Server returned HTTP {e.code}")
        except (ValueError, AttributeError):
            msg = f"Server returned HTTP {e.code}"
        raise ApiError(msg, status=e.code)
    except (urllib.error.URLError, TimeoutError) as e:
        raise ApiError(
            "Couldn't reach the server. Check your internet connection — and if "
            "the server is on a free host it may be waking up, so try again in a minute.\n"
            f"  ({e})"
        )


def lookup(base: str, name: str) -> dict:
    url = f"{base.rstrip('/')}/lookup-json?name={urllib.parse.quote(name)}"
    return _request(url)


def predict_manual(base: str, account: dict) -> dict:
    url = f"{base.rstrip('/')}/predict-json"
    return _request(url, payload=account)


def fetch_accounts(base: str, q: str, label: str, page: int, per_page: int) -> dict:
    params = urllib.parse.urlencode(
        {"q": q or "", "label": label or "all", "page": page, "per_page": per_page}
    )
    url = f"{base.rstrip('/')}/accounts-json?{params}"
    return _request(url)


# ── display ─────────────────────────────────────────────────────────────────────

def display_result(result: dict, true_label: int = None):
    verdict     = result.get("verdict", "?")
    probability = float(result.get("bot_probability", 0))
    confidence  = result.get("confidence", "?")
    name        = result.get("name") or result.get("screen_name", "")
    pct         = f"{probability * 100:.1f}%"

    print()
    print("━" * 52)
    print(f"  Account   : @{result.get('screen_name', '')}  ({name})")
    print(f"  Verdict   : {verdict}  ({confidence} confidence)")
    print(f"  Bot score : {pct}")

    if true_label is not None and true_label in (0, 1):
        actual = "FAKE" if true_label == 1 else "REAL"
        match  = "✓ Correct" if actual == verdict else "✗ Wrong"
        print(f"  Actual    : {actual}  {match}")
    else:
        print("  Actual    : Unknown (not in dataset)")

    print("━" * 52)

    filled = int(probability * 30)
    bar    = "█" * filled + "░" * (30 - filled)
    print(f"  Real ◄ [{bar}] ► Fake")
    print()

    signals = result.get("top_signals") or []
    if signals:
        print("  Key signals:")
        for item in signals:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                print(f"    {str(item[0]):<30} {item[1]}")
    print("━" * 52)
    print()


# ── account listing ──────────────────────────────────────────────────────────────

def render_account_page(data: dict):
    total    = data.get("total", 0)
    page     = data.get("page", 1)
    pages    = data.get("pages", 0)
    per_page = data.get("per_page", 50)
    accounts = data.get("accounts", [])

    start = (page - 1) * per_page + 1 if total else 0
    end   = start + len(accounts) - 1 if accounts else 0

    print()
    print("━" * 60)
    print(f"  Accounts {start:,}–{end:,} of {total:,}")
    print("━" * 60)
    if not accounts:
        print("  No accounts match your search.")
        print("━" * 60)
        return
    print(f"  {'SCREEN NAME':<26}{'LABEL':<7}NAME")
    print("  " + "─" * 56)
    for a in accounts:
        label = "FAKE" if a.get("true_label") == 1 else "REAL"
        handle = ("@" + a.get("screen_name", ""))[:25]
        name   = (a.get("name") or "")[:25]
        print(f"  {handle:<26}{label:<7}{name}")
    print("━" * 60)
    print(f"  Page {page} of {pages}")


def list_accounts(base: str, q: str, label: str, per_page: int):
    page  = 1
    first = True
    while True:
        if first:
            print("  Contacting server (the first request may take up to a minute "
                  "if it needs to wake up)...")
        try:
            data = fetch_accounts(base, q, label, page, per_page)
        except ApiError as e:
            if e.status == 404:
                print("\n  This server doesn't support account listing yet "
                      "(deploy the latest API).\n")
            else:
                print(f"\n  Error: {e}\n")
            return
        first = False

        render_account_page(data)
        pages = data.get("pages", 0)

        # One-shot when not interactive (piped input) or nothing to page through.
        if pages <= 1 or not sys.stdin.isatty():
            return

        try:
            cmd = input("  [Enter]=next  p=prev  <number>=go to page  q=quit : ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if cmd in ("q", "quit"):
            return
        elif cmd in ("p", "prev"):
            page = max(1, page - 1)
        elif cmd.isdigit():
            page = min(max(1, int(cmd)), pages)
        else:
            page = min(pages, page + 1)


# ── manual input ────────────────────────────────────────────────────────────────

def prompt_int(question: str, default: int = 0) -> int:
    while True:
        raw = input(f"  {question} [default {default}]: ").strip()
        if raw == "":
            return default
        try:
            return max(0, int(raw))
        except ValueError:
            print("  Please enter a whole number.")


def prompt_yes_no(question: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    raw  = input(f"  {question} [{hint}]: ").strip().lower()
    if raw == "":
        return default
    return raw in ("y", "yes")


def manual_input(screen_name: str) -> dict:
    print()
    print(f"  '@{screen_name}' is not in the dataset.")
    print("  Look up these numbers on Twitter/X and enter them manually.")
    print("  Press Enter to accept the default if you're unsure.\n")

    account = {
        "screen_name":      screen_name,
        "name":             screen_name,
        "followers_count":  prompt_int("Followers count"),
        "friends_count":    prompt_int("Following count"),
        "statuses_count":   prompt_int("Total tweets (statuses)"),
        "favourites_count": prompt_int("Total likes given"),
        "listed_count":     prompt_int("Listed count (times added to lists)"),
        "description":      "yes" if prompt_yes_no("Does the account have a bio / description?") else "",
        "url":              "yes" if prompt_yes_no("Does the account have a website URL in profile?") else None,
        "location":         "yes" if prompt_yes_no("Does the account have a location set?") else "",
    }
    created = input("  Account creation date (e.g. 2021-03-15), or press Enter to skip: ").strip()
    account["created_at"] = created or None
    return account


# ── core flow ────────────────────────────────────────────────────────────────────

def analyse(base: str, screen_name: str, first_call: bool = False):
    screen_name = screen_name.strip().lstrip("@")
    if not screen_name:
        return

    if first_call:
        print("  Contacting server (the first request may take up to a minute "
              "if it needs to wake up)...")

    try:
        found = lookup(base, screen_name)
    except ApiError as e:
        if e.status == 404:
            # This server has no dataset-lookup endpoint — go straight to manual.
            found = {"found": False}
        else:
            print(f"\n  Error: {e}\n")
            return

    if found.get("found"):
        print(f"\n  Found @{screen_name} in dataset.")
        display_result(found, true_label=found.get("true_label"))
        return

    # Not in dataset — fall back to manual entry.
    account = manual_input(screen_name)
    try:
        result = predict_manual(base, account)
    except ApiError as e:
        print(f"\n  Error: {e}\n")
        return
    display_result(result, true_label=None)


def interactive(base: str):
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║      BotWatch — Fake Account Detector        ║")
    print("║      Type a screen name to analyse           ║")
    print("║      Type 'list' to browse the dataset       ║")
    print("║      Type 'quit' to exit                      ║")
    print("╚══════════════════════════════════════════════╝")

    first = True
    while True:
        print()
        try:
            screen_name = input("  Enter screen name (or 'list'): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Goodbye!")
            break

        if screen_name.lower() in ("quit", "exit", "q"):
            print("  Goodbye!")
            break
        if not screen_name:
            continue
        if screen_name.lower() in ("list", "ls"):
            list_accounts(base, "", "all", 50)
            first = False
            continue

        analyse(base, screen_name, first_call=first)
        first = False


# ── entry point ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="botwatch",
        description="Check whether a Twitter/X account is likely fake or real.",
    )
    parser.add_argument("--name", "-n", help="Screen name to analyse (with or without @)")
    parser.add_argument("--list", "-l", action="store_true",
                        help="List the accounts in the lookup dataset")
    parser.add_argument("--search", "-q", default="",
                        help="Filter the list by screen/display name (with --list)")
    parser.add_argument("--label", choices=["all", "real", "fake"], default="all",
                        help="Filter the list by label (with --list)")
    parser.add_argument("--per-page", type=int, default=50,
                        help="Rows per page when listing (default: 50)")
    parser.add_argument("--api", default=DEFAULT_API,
                        help=f"API base URL (default: {DEFAULT_API})")
    parser.add_argument("--version", "-v", action="version",
                        version=f"BotWatch CLI {VERSION}")
    args = parser.parse_args()

    if args.list:
        list_accounts(args.api, args.search, args.label, args.per_page)
    elif args.name:
        analyse(args.api, args.name, first_call=True)
    else:
        interactive(args.api)


if __name__ == "__main__":
    main()
