# Data folder

This folder holds the parquet files that drive evaluation, organized into one subfolder per
competition format. Every parquet file is tracked via [Git LFS](https://git-lfs.com/), so make
sure LFS is installed before cloning if you want the actual file contents (otherwise you'll get
small pointer files).

```
data/
├── live_leaderboard/     # scored locally — targets shipped
│   ├── template.parquet
│   └── targets.parquet
└── annual_competition/   # targets secret — format validation only
    └── template.parquet
```

## Files at a glance

| File | Format | Rows | Size | Purpose |
|---|---|---|---|---|
| `live_leaderboard/template.parquet` | Apache Parquet | 2,648,987 | ~19 MB | Live-leaderboard submission scaffold — defines exact row order and required columns |
| `live_leaderboard/targets.parquet` | Apache Parquet | 2,648,987 | ~33 MB | Live-leaderboard ground truth — used by `run.py --competition live` to score submissions |
| `annual_competition/template.parquet` | Apache Parquet | — | ~25 KB | Annual-competition submission scaffold — **no targets file; targets are secret** |

Within the live leaderboard, `template.parquet` and `targets.parquet` are row-for-row aligned on
`(id, source_file, date)`, which is what lets `run.py` evaluate submissions with a direct
element-wise comparison. The annual competition ships only a template — its targets are withheld
server-side, so `run.py --competition annual` validates format only and does not score locally.

The two templates share the same column schema; only the row set differs. The schemas below
apply to both formats.

## `template.parquet`

The submission scaffold (present in both `live_leaderboard/` and `annual_competition/`). Copy the
one for your competition, fill in the `pred_*` columns with your model's outputs, and submit the
result. See the **Quick Start** section of the top-level [README](../README.md) for the exact
submission rules.

| Column | Type | Description |
|---|---|---|
| `id` | string | Patient / participant identifier |
| `source_file` | string | Source-dataset identifier (e.g. `AZT1D`) |
| `date` | datetime64[ns] | Sample timestamp, 5-minute spacing |
| `pred_30` | float64 | Your 30-minute-ahead glucose prediction — NaN in the template |
| `pred_60` | float64 | Your 60-minute-ahead glucose prediction — NaN in the template |
| `pred_90` | float64 | Your 90-minute-ahead glucose prediction — NaN in the template |
| `pred_120` | float64 | Your 120-minute-ahead glucose prediction — NaN in the template |

## `targets.parquet`

The held-out ground truth for the **live leaderboard** (`live_leaderboard/targets.parquet`).
**Do not modify.** `run.py --competition live` reads this file to score submissions against
measured CGM values. There is no `targets.parquet` for the annual competition — its targets are
kept secret and scoring runs server-side.

| Column | Type | Description |
|---|---|---|
| `id` | string | Patient / participant identifier (matches the template) |
| `source_file` | string | Source-dataset identifier (matches the template) |
| `date` | datetime64[ns] | Sample timestamp (matches the template) |
| `target_30` | float64 | Measured CGM glucose 30 minutes after `date` |
| `target_60` | float64 | Measured CGM glucose 60 minutes after `date` |
| `target_90` | float64 | Measured CGM glucose 90 minutes after `date` |
| `target_120` | float64 | Measured CGM glucose 120 minutes after `date` |

## How the live-leaderboard test set was built

The live leaderboard's `targets.parquet` is a filtered subset of the full MetaboNet test set published on [metabo-net.org](https://metabo-net.org). We applied the rules below to produce a test set where every sample has the inputs a real-world automated-insulin-delivery (AID) system would need to make a dosing decision.

### Guiding principles

- **CGM-only models shouldn't dominate the leaderboard just because most raw samples lack insulin data.** We require insulin history to be present in every test sample, so models that use the full input set aren't penalized for the gaps in unfiltered data.
- **For training, use everything; for the test set, we guarantee multi-modal coverage.** The raw MetaboNet release — both train and test splits — includes as much data as possible, and for training the more the better. For this competition, however, we'd like to guarantee some data coverage on the test set so that algorithms which successfully use the multi-modal features (such as insulin history and carbs) get properly credited for it. Filtering the test set this way means the leaderboard reflects real predictive performance rather than artifacts of missing data. 

### Sample selection rules

| Rule | Why |
|---|---|
| 24-hour history window, CGM gap ≤ 30 min | Largest gap that can still be meaningfully interpolated |
| 24-hour history window, insulin gap ≤ 2 h (or 0) | Maximum plausible pump-suspend duration; longer gaps would not reflect normal use |
| 24-hour history window, ≥ 1 non-zero / non-NaN `carbs` or `meal_label` sample | Most AID systems rely on carb input, and carbs are a major contributor to glycemic variability |
| 15-minute stride between samples (3 × 5-min steps) | Raw samples overlap heavily; a 15-minute stride keeps the test set large enough to be representative while small enough to evaluate complex models in reasonable time |

### Filtering statistics

We started from the public MetaboNet test split — **22,069,548 rows** across **351 unique `(source_file, id)` groups** from **13 source datasets**. The table below shows how the rules above whittle that down step by step.

| Step | Rows dropped | Rows remaining |
|---|---|---|
| Initial test set | — | 22,069,548 |
| Rows with NaN targets | 3,336,797 | 18,732,751 |
| Lookback criterion *(breakdown below)* | 10,786,072 | 7,946,679 |
| 15-minute stride (3 × 5-min steps) | 5,297,692 | **2,648,987** |

#### Lookback criterion — breakdown of dropped rows

| Reason | Rows dropped |
|---|---|
| Insufficient lookback (<24 h available) | 77,409 |
| Current-slot CGM is NaN | 235,730 |
| CGM gap > 30 min in window | 4,511,858 |
| Insulin 0/NaN run > 120 min in window | 3,195,115 |
| No `carbs > 0` or `meal_label` in window | 2,765,960 |

#### Source datasets

The final test set covers **279 unique `(source_file, id)` pairs** across **9 source datasets**:

**Kept (9):** `AZT1D`, `BrisT1D`, `CTR3`, `HUPA-UCM`, `IOBP2`, `Loop`, `PEDAP`, `ReplaceBG`, `ShanghaiT1DM`

**Fully dropped by filtering (4):**
- `DCLP3`, `DCLP5`, `Flair` — no carbohydrate information available, so the carbs / meal_label rule excludes every row.
- `T1D-UOM` — only MDI (multiple-daily-injection) participants in the test set, which leaves too many insulin gaps to satisfy the insulin-coverage rule.

## See also

- Top-level [`README.md`](../README.md) — installation, submission format, competition formats, and `run.py` usage
- `run.py` — validates submissions against the chosen competition's `template.parquet`; for the live leaderboard (`--competition live`) it also scores against `live_leaderboard/targets.parquet`
