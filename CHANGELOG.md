# Changelog

## v1.0 — 2026-06-23

First public release of **BotWatch — Fake Account Detector**, a machine-learning
tool that flags likely fake/bot Twitter/X accounts (99% F1, 0.997 AUC-ROC on the
Cresci-2017 benchmark).

### Download — standalone CLI (Windows)

Grab **`botwatch.exe`** from the assets below. No Python, no install, no setup —
it talks to the hosted BotWatch API.

```
botwatch                     # interactive mode
botwatch --name elonmusk     # analyse one account
botwatch --list              # browse the labelled dataset
botwatch --list -q bask --label real   # search the list, real accounts only
```

If a screen name is in the bundled dataset you get the model's verdict plus the
ground-truth label; otherwise you're prompted to enter the account's stats and it
predicts from those. The first request may take ~30–60s while the free-tier
server wakes up.

- **Requirements:** 64-bit Windows + an internet connection.
- **First run:** Windows SmartScreen may warn about an "unknown publisher" —
  click *More info → Run anyway*.

### Also part of this project

- **Web app** — analyse accounts and browse the dataset in any browser:
  <https://botwatch-6qpn.onrender.com>
- **Chrome extension (BotWatch)** — live real/fake verdicts while browsing
  Twitter/X.
- **JSON API** — `POST /predict-json` for programmatic access.

### Notes

- The model is trained on Cresci-2017 (2017 data); very high-profile or modern
  accounts may be classified with lower confidence.
