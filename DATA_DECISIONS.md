# Data integrity decisions

A running record of decisions that changed what is in the database, so they
can be written up honestly in the thesis (methodology + limitations) rather
than reconstructed from memory later. Newest first.

---

## 2026-07-25 — Removed 100 news rows from untrusted sources

**What**: Deleted 100 rows from `fact_news` whose publisher was not in
`TRUSTED_NEWS_SOURCES`, and rebuilt `fact_sentiment_daily` for the 22
affected `(asset_id, d)` pairs from the trusted news that remained.
Script: `src/scripts/purge_untrusted_news.py` (idempotent, has `--dry-run`).

**Why they existed**: The Airflow DAG loads `.env.airflow` via
`set -a && source .env.airflow`. `TRUSTED_NEWS_SOURCES` was unquoted but
contains spaces, so bash truncated the assignment at the first space and
tried to execute the remainder as a command. The variable ended up empty,
`src/config.py` turned that into an empty tuple, and
`src/extract/news_rss.py` treats an empty tuple as falsy — skipping source
filtering entirely. Fixed by quoting the value.

**Scope**: All 100 rows fell in 2026-04-02 → 2026-04-09, coinciding with the
`cloud_backfill*.sh` runs. By ticker: TSLA 45, AAPL 17, MSFT 17, GC=F 11,
EURUSD=X 6, BTC-USD 3, THBUSD=X 1.

**Impact**: 6 ticker-days lost their only news and no longer have a
sentiment row (TSLA, GC=F, BTC-USD, EURUSD=X ×2, THBUSD=X — one day each);
16 pairs were recomputed from trusted news only. AAPL and MSFT lost no days.
Pooled sentiment-model accuracy after the purge: 0.635 vs 0.558 baseline,
walk-forward range 0.425–0.635, 1 of 3 folds beating its own baseline.

**Deliberately NOT deleted**: ~1,572 rows recorded with source name
`news.google.com` (2025-12-16 → 2026-03-13). These predate per-article
source extraction, so `_guess_source()` stored the *feed* domain instead of
the real publisher. They may well have passed the filter at ingest time —
it simply isn't recoverable from what was stored. They are the bulk of the
earliest and longest sentiment series, so removing them on a technicality
would destroy far more real signal than the contamination it targets. The
exclusion is by source name in `LEGACY_PLACEHOLDER_SOURCES`, not a date
cutoff, so the rule stays explicit.

**Limitation to state in the thesis**: sentiment values before 2026-03-14
come from articles whose individual publisher was not recorded, so the
trusted-source filter cannot be independently verified for that period.

---

## 2026-07-25 — Airflow ran only 7 of 30 tickers

**What**: `.env.airflow` had `TICKERS` set to 7 symbols
(AAPL, MSFT, TSLA, BTC-USD, EURUSD=X, THBUSD=X, GC=F) while `.env` used for
local runs had all 30. Synced to all 30.

**Why it matters**: News/sentiment cannot be backfilled (Google News RSS
returns only current headlines), so only the scheduled daily run accumulates
it. Any ticker missing from the Airflow list permanently lost a day of
sentiment coverage for every day it stayed missing. This — not the RSS query
wording — is the main reason coverage was so uneven: AAPL/MSFT/TSLA reached
~90 days while the other 23 tickers had almost none until a few manual runs
in July 2026.

**Limitation to state in the thesis**: sentiment coverage per ticker is a
function of when that ticker entered the scheduled pipeline, not of news
volume. Coverage depth is therefore not comparable across tickers before
2026-07-25.

---

## 2026-07-25 — Recomputed `return_1d` / `pct_change` for all price rows

**What**: Recomputed both columns for every `fact_price_daily` row from the
stored close-price history using SQL `LAG`, via
`src/scripts/backfill_price_returns.py`. Pure derived arithmetic on data
already in the table — no new values invented.

**Why**: `run_daily.py` fetched only a short lookback window (14d Yahoo /
60d Stooq) and computed `return_1d` with `shift(1)` *within that batch*, so
the earliest row of each run had no visible previous close and became NULL.
Because the upsert is `ON CONFLICT DO UPDATE`, this overwrote correct values
with NULL on every run. A single NULL then nulled `volatility_20` for the
following 20 rows, which silently shortened the usable model window.
`run_daily.py` now recomputes from the full DB history after every upsert.

---

## 2026-07-25 — Technical indicators moved into the daily pipeline

**What**: `run_daily.py` now computes and upserts `fact_technical_daily`
from full DB history on every run. Previously this only happened when
`src/scripts/backfill_technical_indicators.py` was run by hand, so the table
had silently fallen ~6 days behind, and the dashboard's "latest signal" was
stale by nearly two weeks.

---

## Known, accepted data anomaly

`CL=F` (WTI crude) has a negative close of **-37.63 on 2020-04-20**, which
trips the `non_positive_close_price` DQ check. This is a real historical
event (WTI futures settled negative during the 2020 storage glut), not a
data error, and is deliberately retained.

It is listed in `ACCEPTED_ANOMALIES` in `src/dq/checks.py`, which excludes it
from the check *count* (so the report's overall status can reach PASS and
therefore mean something) while still printing it in an "Accepted anomalies"
section on every run, so it is never silently forgotten. The exclusion
matches on the `(ticker, date)` pair, so accepting this row cannot excuse a
different ticker that happens to share the date. Adding an entry there is a
claim that the data is right and the check is too strict for that row — not
a way to quiet a real problem.
