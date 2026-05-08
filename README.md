# Fake Social Media Account Detector

A machine learning system that detects fake and bot Twitter accounts using a
Random Forest classifier trained on the Cresci-2017 dataset. The model achieves
**99% F1 score** and **0.997 AUC-ROC** on held-out test data. Predictions are
fully explainable via SHAP values.

---

## Table of contents

- [Project overview](#project-overview)
- [Dataset](#dataset)
- [Project structure](#project-structure)
- [Setup — step by step](#setup--step-by-step)
- [Running the notebooks](#running-the-notebooks)
- [Using the CLI](#using-the-cli)
- [How it works](#how-it-works)
- [Features used](#features-used)
- [Results](#results)
- [Limitations](#limitations)
- [Future work](#future-work)
- [Troubleshooting](#troubleshooting)

---

## Project overview

Fake and bot accounts on social media platforms distort public discourse,
inflate follower counts, and spread misinformation. This project builds a
machine learning pipeline that:

1. Loads a labelled dataset of real and fake Twitter accounts
2. Engineers meaningful features from raw account metadata
3. Trains a Random Forest classifier to distinguish real from fake accounts
4. Evaluates the model using precision, recall, F1, and AUC-ROC
5. Explains individual predictions using SHAP values
6. Exposes predictions via a command line interface

---

## Dataset

**Cresci-2017** — the most widely cited benchmark dataset for Twitter bot
detection research.

- **Source:** [Bot Repository — Indiana University Observatory on Social Media](https://botometer.osome.iu.edu/bot-repository/datasets.html)
- **Total accounts:** 14,368 labelled Twitter accounts
- **Format:** CSV files, one row per account

### Account groups

| Folder                   | Label    | Count | Description                        |
| ------------------------ | -------- | ----- | ---------------------------------- |
| `genuine_accounts`       | Real (0) | 3,474 | Verified human accounts            |
| `social_spambots_1`      | Fake (1) | 991   | Bots mimicking human behaviour     |
| `social_spambots_2`      | Fake (1) | 3,457 | Bots mimicking human behaviour     |
| `social_spambots_3`      | Fake (1) | 464   | Bots mimicking human behaviour     |
| `traditional_spambots_1` | Fake (1) | 1,000 | Classic spam bots                  |
| `fake_followers`         | Fake (1) | 3,351 | Accounts inflating follower counts |

> The dataset is provided for academic research only. Twitter content is
> subject to the Twitter Developer Agreement and Policy. You must download
> it separately — it is not included in this repository.

---

## Project structure

```
fake-account-detector/
│
├── data/                          # Place downloaded CSV folders here
│   ├── genuine_accounts/
│   │   └── users.csv
│   ├── social_spambots_1/
│   │   └── users.csv
│   ├── social_spambots_2/
│   │   └── users.csv
│   ├── social_spambots_3/
│   │   └── users.csv
│   ├── traditional_spambots_1/
│   │   └── users.csv
│   ├── fake_followers/
│   │   └── users.csv
│   └── .gitkeep
│
├── models/                        # Populated after running the notebooks
│   └── .gitkeep
│
├── notebooks/                     # Run these in order — see below
│   ├── 01_explore_data.ipynb
│   ├── 02_feature_engineering.ipynb
│   ├── 03_preprocessing.ipynb
│   ├── 04_train_model.ipynb
│   └── 05_explainability.ipynb
│
├── src/                           # Core reusable code
│   ├── __init__.py                # Makes src/ a Python package — must exist
│   └── predict.py                 # Feature engineering + prediction logic
│
├── cli.py                         # Command line interface
├── requirements.txt               # Python dependencies
├── .gitignore
└── README.md
```

> **Important:** The `data/` and `models/` folders are excluded from git.
> You must populate them yourself by following the setup steps below.
> The `data/` folder will contain your downloaded CSVs. The `models/`
> folder will be populated when you run the notebooks.

---

## Setup — step by step

### Requirements

- Python **3.9 or higher**
- pip
- A Jupyter-compatible editor — PyCharm (Community or Professional) with
  Jupyter support, or Jupyter running in the browser

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/fake-account-detector.git
cd fake-account-detector
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

You should see `(.venv)` at the start of your terminal prompt confirming
the environment is active.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

This installs pandas, numpy, scikit-learn, shap, matplotlib, and Jupyter.
It may take a few minutes the first time.

### 4. Download the dataset

1. Go to [https://botometer.osome.iu.edu/bot-repository/datasets.html](https://botometer.osome.iu.edu/bot-repository/datasets.html)
2. Find and download the **Cresci-2017** dataset
3. Unzip the download
4. Copy the following folders into the `data/` directory of this project:

```
data/genuine_accounts/
data/social_spambots_1/
data/social_spambots_2/
data/social_spambots_3/
data/traditional_spambots_1/
data/fake_followers/
```

Each folder must contain a `users.csv` file. Verify your setup by running:

```bash
ls data/
```

You should see the folder names listed alongside `.gitkeep`.

### 5. Verify src/**init**.py exists

The `src/` folder must contain an empty file called `__init__.py`. This
makes it a Python package so `cli.py` can import from it. If it is
missing for any reason, create it:

```bash
# macOS / Linux
touch src/__init__.py

# Windows
type nul > src\__init__.py
```

---

## Running the notebooks

> **The notebooks must be run in order, from 01 through to 05.**
> Each notebook produces files that the next notebook depends on.
> Running them out of order, or skipping one, will cause errors.

Open each notebook in the `notebooks/` folder and run all cells from
top to bottom. In PyCharm, open the `.ipynb` file and use the Run All
button. In Jupyter browser, use Kernel → Restart & Run All.

### 01 — explore_data.ipynb

Loads all CSV files, combines them into one DataFrame, and explores the
data — column names, missing values, and the statistical differences
between real and fake accounts.

**Produces:** nothing saved to disk (exploration only)

### 02 — feature_engineering.ipynb

Builds 13 features from the raw columns across three categories: direct
counts, engineered ratios (e.g. `tweet_frequency`, `follower_friend_ratio`),
and binary flags (e.g. `has_description`, `has_url`).

**Produces:**

```
data/features.csv
data/feature_columns.csv
```

### 03 — preprocessing.ipynb

Fills 1,000 missing values using the training median, applies log scaling
to skewed count columns, standardises all features using StandardScaler,
and splits the data 80/20 into training and test sets using stratified
sampling.

**Produces:**

```
data/X_train.npy
data/X_test.npy
data/y_train.npy
data/y_test.npy
models/scaler.joblib
```

### 04 — train_model.ipynb

Trains a Random Forest classifier (100 trees, `class_weight="balanced"`)
on the preprocessed training set. Evaluates on the held-out test set and
prints a classification report, confusion matrix, and feature importances.

**Produces:**

```
models/random_forest_model.joblib
```

### 05 — explainability.ipynb

Computes SHAP values for the entire test set and generates four charts:
a dot summary plot, a bar importance chart, and two waterfall charts
showing the reasoning behind individual fake and real predictions.

**Produces:**

```
models/shap_summary.png
models/shap_bar.png
models/shap_waterfall_fake.png
models/shap_waterfall_real.png
```

---

## Using the CLI

Once all five notebooks have been run successfully the CLI is ready.
Always run it from the **project root directory** (not from inside `src/`).

### Interactive mode

```bash
python cli.py
```

You will be prompted to type a Twitter screen name one at a time.
Type `quit` to exit.

### Single account — direct lookup

```bash
python cli.py --name 0918Bask
```

### Example output — account found in dataset

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Account   : @0918Bask  (TASUKU HAYAKAWA)
  Verdict   : REAL  (High confidence)
  Bot score : 3.2%
  Actual    : REAL  ✓ Correct
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Real ◄ [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] ► Fake

  Key signals:
    Favourites (likes) given       12453
    Tweets per day                 4.21
    Follower / following ratio     0.63
    Total tweets                   2177
    Has bio                        Yes
    Has location                   Yes
    Has website URL                No
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Example output — account not in dataset (manual fallback)

If the screen name is not found in the dataset, the CLI asks you to enter
the account's stats manually. You can look these up by visiting the
account on Twitter/X in a browser.

```
  '@elonmusk' is not in the dataset.
  You can look up these numbers on Twitter/X and enter them manually.
  Just press Enter to accept the default (0) if you are unsure.

  Followers count [default 0]: 170000000
  Following count [default 0]: 700
  Total tweets (statuses) [default 0]: 45000
  Total likes given [default 0]: 85000
  Listed count (times added to lists) [default 0]: 150000
  Does the account have a bio / description? [y/N]: y
  Does the account have a website URL in profile? [y/N]: y
  Does the account have a location set? [y/N]: y
  Account creation date (e.g. 2021-03-15), or press Enter to skip: 2009-06-02
```

No ground truth is available for accounts outside the dataset, so
`Actual` will show as `Unknown (not in dataset)`.

---

## How it works

### Step 1 — Data collection

Six groups of labelled Twitter accounts are loaded from CSV and combined
into a single DataFrame with a binary label column (0 = real, 1 = fake).

### Step 2 — Feature engineering

Thirteen features are engineered from raw account metadata. The key
insight: real accounts average 4,669 likes given vs just 23 for fake
accounts — a 200× difference that becomes the model's strongest signal.

### Step 3 — Preprocessing

Three problems are addressed: missing values (filled with training median),
skewed distributions (compressed with log scaling), and class imbalance
(handled with `class_weight="balanced"` in the classifier).

### Step 4 — Model training

A Random Forest builds 100 decision trees, each trained on a random
sample of the data. At prediction time every tree votes and the majority
wins. This approach is robust to outliers and provides built-in feature
importance scores.

### Step 5 — Explainability

SHAP (SHapley Additive exPlanations) decomposes each prediction into
per-feature contributions — showing exactly how much each clue pushed the
score toward fake or real for any individual account.

---

## Features used

| Feature                 | Type    | Description                             |
| ----------------------- | ------- | --------------------------------------- |
| `statuses_count`        | Direct  | Total tweets ever posted                |
| `followers_count`       | Direct  | Number of followers                     |
| `friends_count`         | Direct  | Number of accounts followed             |
| `favourites_count`      | Direct  | Total likes given                       |
| `listed_count`          | Direct  | Times added to Twitter lists            |
| `follower_friend_ratio` | Ratio   | followers ÷ (friends + 1)               |
| `tweet_frequency`       | Ratio   | statuses ÷ (account_age_days + 1)       |
| `favourites_per_tweet`  | Ratio   | favourites ÷ (statuses + 1)             |
| `listed_per_follower`   | Ratio   | listed ÷ (followers + 1)                |
| `has_description`       | Flag    | 1 if account has a bio, else 0          |
| `has_url`               | Flag    | 1 if account has a website URL, else 0  |
| `has_location`          | Flag    | 1 if account has a location set, else 0 |
| `account_age_days`      | Derived | Days since account creation             |

---

## Results

| Metric                                 | Score      |
| -------------------------------------- | ---------- |
| Accuracy                               | 99%        |
| F1 — fake class                        | 0.99       |
| F1 — real class                        | 0.98       |
| AUC-ROC                                | 0.9970     |
| False positives (real flagged as fake) | 11 / 695   |
| False negatives (bots missed)          | 19 / 1,853 |

### Top features by SHAP importance

| Rank | Feature                 | Contribution |
| ---- | ----------------------- | ------------ |
| 1    | `favourites_count`      | 30.9%        |
| 2    | `favourites_per_tweet`  | 25.0%        |
| 3    | `tweet_frequency`       | 14.4%        |
| 4    | `statuses_count`        | 10.7%        |
| 5    | `follower_friend_ratio` | 6.7%         |

Engagement behaviour — how much an account interacts with other content —
is by far the strongest predictor of authenticity.

---

## Limitations

- **Dataset age** — Cresci-2017 was collected in 2017. Modern bots are
  considerably more sophisticated and may evade detection by mimicking
  engagement patterns more closely.

- **Out-of-distribution accounts** — Very high-profile accounts such as
  public figures with tens of millions of followers have statistics far
  outside the training distribution. The model classifies them correctly
  but with reduced confidence, as it has never seen profiles at that scale.

- **No live API access** — Twitter's API is now paywalled. The CLI
  supports manual entry of account statistics for accounts outside the
  dataset but cannot perform automatic live lookups.

- **Profile metadata only** — The model uses account metadata, not tweet
  content. Adding NLP-based content features (sentiment, hashtag patterns,
  repetitive text) would likely improve detection of sophisticated bots.

---

## Future work

- Train on a more recent dataset (TwiBot-22) to capture modern bot behaviour
- Add NLP content features extracted from tweet text
- Build a web dashboard using Flask and a simple HTML frontend
- Support bulk analysis — accept a CSV of screen names and output results
- Explore graph-based features using the follower network structure
- Compare performance against deep learning approaches (LSTM, GNN)

---

## Troubleshooting

### `ValueError: No objects to concatenate` when running cli.py

The CSV folders are not in the expected location. Verify with:

```bash
ls data/
```

You should see `genuine_accounts/`, `social_spambots_1/` etc. listed
directly inside `data/`. If the folders are nested one level deeper
(e.g. `data/cresci-2017/genuine_accounts/`) move them up one level.

### `TypeError: Cannot subtract tz-naive and tz-aware datetime objects`

This occurs in notebook 02 when computing account age. Make sure your
`pd.to_datetime()` call includes `utc=True` and the reference date is
defined as `pd.Timestamp("2017-01-01", tz="UTC")`.

### `AssertionError: shape of shap_values does not match data matrix`

This is a SHAP version compatibility issue in notebook 05. After computing
SHAP values, check the shape returned:

```python
print(type(shap_values), np.array(shap_values).shape)
```

Then extract the fake class accordingly:

```python
# Older SHAP — returns a list of two arrays
shap_fake = shap_values[1]

# Newer SHAP — returns a single 3D array
shap_fake = shap_values[:, :, 1]
```

### `ModuleNotFoundError: No module named 'src'`

Two possible causes:

1. `src/__init__.py` does not exist — create it (see Setup step 5)
2. You ran `python src/cli.py` instead of `python cli.py` — always run
   from the project root

### Jupyter kernel not found in PyCharm

Make sure your virtual environment is selected as the Python interpreter.
In PyCharm go to Settings → Project → Python Interpreter and select the
`.venv` environment. Then open any notebook and select the same interpreter
as the kernel.

---

## Dependencies

```
pandas>=1.5.0
numpy>=1.23.0
scikit-learn>=1.2.0
joblib>=1.2.0
shap>=0.42.0
matplotlib>=3.6.0
jupyter>=1.0.0
ipykernel>=6.0.0
```

Install all at once:

```bash
pip install -r requirements.txt
```

---

## Academic citation

This project uses the Cresci-2017 dataset. If you use this work please
cite the original paper:

> Cresci, S., Di Pietro, R., Petrocchi, M., Spognardi, A., & Tesconi, M.
> (2017). _The paradigm-shift of social spambots: Evidence, theories, and
> tools for the arms race._ In Proceedings of the 26th International
> Conference on World Wide Web Companion (pp. 963–972).
