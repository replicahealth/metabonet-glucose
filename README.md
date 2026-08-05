# Glucose Prediction Submission ToolKit

This repository contains the evaluation script for the MetaboNet-Glucose prediction benchmark. 

[🏆 View Leaderboard 🏆](https://huggingface.co/spaces/MetabonetBench/leaderboard-space)

## Installation

> ⚠️ **Read this first — this repo uses [Git LFS](https://git-lfs.com) for the parquet files in `data/`.**
> If you clone without Git LFS installed, you will get tiny pointer files (a few hundred bytes) instead of the actual data, and `run.py` will not work.

### Step 1 — Install Git LFS (once per machine)

Install the Git LFS client:

- **macOS:** `brew install git-lfs`
- **Ubuntu / Debian:** `sudo apt-get install git-lfs`
- **Windows / other:** download from [git-lfs.com](https://git-lfs.com)

Then register it with your Git install (only needed once per machine):

```bash
git lfs install
```

### Step 2 — Clone the repo

With LFS installed, a normal `git clone` will automatically download the real parquet files:

```bash
git clone https://github.com/replicahealth/glucose-prediction-submission-toolkit.git
cd glucose-prediction-submission-toolkit
```

**Sanity check:** `ls -lh data/live_leaderboard/` should show `template.parquet` at ~19 MB and `targets.parquet` at ~33 MB. If they're only a few hundred bytes, you got pointer files — see "Already cloned without LFS?" below.

### Step 3 — Install Python dependencies

```bash
uv venv .env
source .env/bin/activate  # On Windows: .env\Scripts\activate
uv pip install -r requirements.txt
```

### Already cloned without LFS?

Don't re-clone. Install Git LFS as in Step 1, then from inside the repo run:

```bash
git lfs install
git lfs pull
```

This replaces the pointer files with the actual parquet contents in place.


## Competition formats

MetaboNet runs two competition formats, each with its own data folder under `data/`:

| Format | `--competition` value | Template | Targets | `run.py` behavior |
|---|---|---|---|---|
| **Live leaderboard** | `live` | `data/live_leaderboard/template.parquet` | `data/live_leaderboard/targets.parquet` (shipped) | Validates format **and** scores locally (RMSE, MARD, DTS) |
| **Annual competition** | `annual` | `data/annual_competition/template.parquet` | Secret — held server-side | Validates format **only** (no local scoring) |

`run.py` **requires** the `--competition` flag so you always know which format you're
targeting. The submission format (columns and rules) is identical for both; only the template
you validate against — and whether scoring runs locally — differ.

## Quick Start (live leaderboard)

The steps below are for submitting to the **live leaderboard** (`--competition live`). For the
**annual competition**, see [Annual Competition](#annual-competition) below.

1. **Generate and format predictions**: Use your model to create predictions for the MetaboNet test set, then save them as a parquet file. Each row must include:
   - `pred_30`: 30-minute ahead glucose prediction
   - `pred_60`: 60-minute ahead glucose prediction
   - `pred_90`: 90-minute ahead glucose prediction
   - `pred_120`: 120-minute ahead glucose prediction

   The file must:
   - Be in parquet format
   - Have the exact same rows and columns as `data/live_leaderboard/template.parquet` (same `id`, `source_file`, and `date` combinations)
   - Keep rows in the same order as the template
   - Include all four prediction columns (`pred_30`, `pred_60`, `pred_90`, `pred_120`)
   - Fully populate **at least one** prediction column. You can compete on a single horizon or any subset. Each populated column must contain no missing values, and any horizons you skip must be left **entirely empty** (all NaN). Partially filled columns are rejected.

   For details on what's in `data/` and how the test set was built, see [`data/README.md`](data/README.md).

   **Preview of submission format:**

   | id | source_file | date                | pred_30 | pred_60 | pred_90 | pred_120 |
   |----|-------------|---------------------|---------|---------|---------|----------|
   | 16 | AZT1D       | 2024-01-18 01:00:00 | NaN     | NaN     | NaN     | NaN      |
   | 16 | AZT1D       | 2024-01-18 01:05:00 | NaN     | NaN     | NaN     | NaN      |
   | 16 | AZT1D       | 2024-01-18 01:10:00 | NaN     | NaN     | NaN     | NaN      |
   | 16 | AZT1D       | 2024-01-18 01:15:00 | NaN     | NaN     | NaN     | NaN      |
   | 16 | AZT1D       | 2024-01-18 01:20:00 | NaN     | NaN     | NaN     | NaN      |

2. **Validate and evaluate**:
   ```bash
   python run.py your_predictions.parquet --competition live                 # Default: 60-minute horizon
   python run.py your_predictions.parquet --competition live --horizon 30     # Evaluate 30-minute horizon only
   python run.py your_predictions.parquet --competition live --horizon all    # Evaluate all horizons + overall (all horizons combined)
   ```
   
   Available `--horizon` options: `30`, `60`, `90`, `120`, or `all` (defaults to `60`)

   Example output:
   ```
   🔍 Loading files...
   ✅ Files loaded successfully

   📋 Validating format...
   ✅ Format validation passed!

   📊 Calculating metrics for horizon: 60...

   ============================================================
                       EVALUATION RESULTS
   ============================================================

   📈 60 Min Ahead Predictions:
      RMSE: 53.17 mg/dL
      MARD: 33.51 %

      DTS Error Grid Zones:
      • Zone A (Clinically Accurate):     38.2%
      • Zone B (Benign Errors):           47.3%
      • Zone C (Overcorrection):          13.5%
      • Zone D (Failure to Detect):       0.9%
      • Zone E (Erroneous Treatment):     0.0%

   ============================================================

   ✅ Format is valid! You are ready to submit!
   🚀 Submit your predictions at:
      https://huggingface.co/spaces/MetabonetBench/leaderboard-space

   ============================================================
   ```

3. **Submit**: Once validation passes, submit your predictions at:
https://huggingface.co/spaces/MetabonetBench/leaderboard-space


## Annual Competition

The **annual competition** uses a separate, smaller test set whose ground-truth targets are
**secret** — they are held server-side so the competition stays a true held-out evaluation.
Because the targets aren't shipped with the repo, `run.py` can only **validate the format** of
your submission against `data/annual_competition/template.parquet`; it does **not** score
locally. Scoring happens server-side after you submit.

The submission format is identical to the live leaderboard (same `pred_30`/`pred_60`/`pred_90`/
`pred_120` columns and the same rules: at least one horizon fully populated, skipped horizons
left entirely empty). The only differences are the template you validate against and that no
metrics are printed.

1. **Generate and format predictions** exactly as for the live leaderboard, but match the rows
   and columns of `data/annual_competition/template.parquet`.

2. **Validate the format** (no horizon needed — nothing is scored locally):
   ```bash
   python run.py your_predictions.parquet --competition annual
   ```
   On success you'll see the format-validation report and a "ready to submit" message, with no
   metrics table.

3. **Submit**: Once validation passes, submit your predictions at:
https://huggingface.co/spaces/MetabonetBench/leaderboard-space


## Files

- `run.py` - Validation and evaluation script (`--competition live` scores; `--competition annual` validates format only)
- `metrics.py` - Metric calculation functions (RMSE, MARD, DTS Error Grid)
- `data/live_leaderboard/template.parquet` - Live-leaderboard submission template (required format)
- `data/live_leaderboard/targets.parquet` - Live-leaderboard ground truth used for local scoring
- `data/annual_competition/template.parquet` - Annual-competition submission template (targets are secret; format validation only)


