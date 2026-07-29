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

---

## 2026-07-29 — `source` column on `fact_fundamentals_quarterly`

**What**: added `source TEXT`; the 106 pre-existing rows were tagged
`'yfinance'` in place. No values changed.

**Why**: the table was about to hold rows from two providers that disagree on
period-end dates (yfinance rounds to month end, EDGAR uses the actual fiscal
date), and there was no way to tell them apart afterwards. Provenance also
has to be stated in the thesis, and reconstructing it from the data would not
have been possible.

---

## 2026-07-29 — Q4 fundamentals are NOT derived (limitation, accepted)

**What**: 181 of the ~334 ticker-years available from EDGAR have only three
tagged quarters. `_derive_q4_rows` in `src/extract/fundamentals_edgar.py`
reconstructs the fourth as FY minus Q1+Q2+Q3, and is **off by default**. Track
B therefore has a systematic Q4 gap in those years.

**Why not just turn it on**: a 10-K reports the full year; the fourth quarter
exists only as a remainder. Subtracting is arithmetic on reported figures, not
an estimate, so this looked safe. Measuring it said otherwise:

- Graded on the 131 ticker-years that *do* have a filed Q4, requiring the
  year and its quarters to come from one tag in one filing: **106/106 correct
  on revenue, 101/101 on net income**.
- That result does not transfer. Agreement is only possible when the 10-K
  restates its quarters, and such filings also tag Q4 — so **0 of the 181
  years that need deriving can be verified this way**.
- The only method those years permit is the year minus the quarters as first
  filed in each 10-Q. Graded on the 20 comparable years: **15 correct, 5 wrong
  by 2.4%–40.7%.** Roughly a 25% error rate, undetectable at load time, in the
  quarter that carries the annual result.

A visible gap is worth more than ~180 rows of which a quarter are wrong in
unknown places. Documented as a limitation instead.

---

## 2026-07-29 — Two EDGAR parsing rules that change stored values

**Mis-tagged annual figures dropped** (`_drop_mistagged_quarters`): Oracle's
10-Ks label full-year revenue with a valid 91-day start/end for FY2018-FY2022.
The dates pass every structural check, so the value is compared against the
fiscal year containing it and dropped when it equals that year. The threshold
is 0.95, near-equality, deliberately: a first attempt at 0.6 discarded Tesla's
quarter ending 2012-12-31, which really was 74% of FY2012 because of the Model
S ramp. A nine-month YTD figure mis-tagged as a quarter would land near 75%
and this check does not claim to find those.

**Per-share figures use the latest filing** (`_first_reported`, `prefer`):
every other field keeps the value as first reported, which is what a
point-in-time backtest may see. EPS cannot: Apple tagged 14.50 for the quarter
ending 2013-12-28 and re-tagged the same quarter 2.07 after the 2014 7:1
split. Taking the earliest per period puts a 7x cliff mid-FY2014 that no
company event explains. Splits are presentational, and our price history is
split-adjusted too, so the adjusted figure is the consistent one. The cost is
that a genuine EPS restatement is absorbed silently.

**Known residue**: this does not fully repair EPS. Apple's FY2012 quarters are
only ever tagged pre-split, while FY2012's annual EPS was re-tagged at 6.31 in
a later 10-K, because annual comparatives get restated and individual quarters
that old do not. No choice of filing reconciles the two. Derived Q4 rows
therefore never carry EPS at all, and EPS from EDGAR should be treated as
unreliable across a split boundary.

---

## 2026-07-29 — yfinance fundamentals replaced by SEC EDGAR

**What**: `fact_fundamentals_quarterly` was rebuilt from EDGAR. The 106
yfinance rows were deleted and 1,134 EDGAR rows loaded, covering the same 21
equities from 2007-09-30 to 2026-06-30. Backup of the old table:
`backups/fact_fundamentals_quarterly_20260729_113555.sql` (gitignored).
Reload with `python -m src.scripts.load_fundamentals_edgar --apply`.

**Why a replacement and not a merge**: the primary key is
`(asset_id, fiscal_period_end)` and the providers date the same quarter
differently — yfinance rounds to month end (2026-03-31), EDGAR gives the
actual fiscal close (2026-03-28). Loaded together, one quarter becomes two
rows under two keys and every Track B aggregate double-counts, with no query
able to separate them afterwards.

**Why EDGAR wins**: 10.7x the history; real fiscal period ends; and
`announced_d` from the filing itself — often the 8-K earnings release, which
is when the market actually learned the figure — rather than approximated
from an earnings calendar. Agreement with yfinance on the 52 overlapping
quarters was 51/51 on net income and 46/51 on revenue, the exceptions being
definitional (see the entry on XOM/WMT revenue lines).

**Verified after loading**: 0 duplicate quarters, 0 rows announced on or
before their period end (no look-ahead), 0 zero or negative revenue.

---

## 2026-07-29 — Three extraction bugs found by loading, not by review

Each produced plausible numbers and raised nothing. All three were caught by
checking the loaded table rather than by reading the extractor.

**One quarter stored twice** (`_dedupe_near_period_ends`): NVIDIA's quarter
ending 2010-08-01 is re-dated 2010-07-31 by a 2012 filing, same revenue and
net income. Both survived as separate primary keys. Quarters are ~91 days
apart, so period ends within 5 days are now collapsed, keeping the one
announced first.

**Zero treated as a reported figure** (`skip_zero`): Oracle's 10-Qs carry
`SalesRevenueNet` = 0 for three quarters of FY2009 while stating the real
5.45bn under `Revenues`. Because `SalesRevenueNet` ranks higher the zero won,
and downstream `revenue_growth_qoq` divided by it and became infinite — which
turned the correlation for that feature into NaN for *every* ticker, printed
as `r=+nan`. Zero now means "not reported" for revenue only; net income and
free cash flow can legitimately be zero.

**A sub-line outranking the top line** (`SUBLINE_RATIO`): Oracle tags
`SalesRevenueNet` with a single product line — 458m for the quarter ending
2010-02-28 — while total revenue of 6,404m sits under the lower-ranked
`Revenues`. Ordering cannot fix this, since for Apple and Amazon
`SalesRevenueNet` *is* the total. A lower-priority tag now wins when it
exceeds the chosen one by more than 1.5x. The threshold matters: tags that
differ over what counts as revenue differ by a few percent (Walmart's
membership fees, Exxon's other income) and JPMorgan's `Revenues` exceeds
`RevenuesNetOfInterestExpense` by 14% with the bank measure needing to win. A
sweep of all 21 equities found this only in ORCL, 4 of its 59 quarters.

**A guard that deleted good data**: the mis-tagged-annual check was written as
"quarter larger than 95% of its year", which also fires when the *annual*
figure is the wrong line. Oracle's FY2010 total is tagged 2.29bn, so three
correct quarters of ~5-6bn were silently removed. It now tests for
near-equality in both directions.

**Also fixed in `src/models/dataset_fundamentals.py`**: `pct_change()` was
using the pandas default `fill_method='ffill'`, which forward-fills a missing
quarter and so reports 0% growth for a quarter we have no figure for, then a
doubled change for the next. Now `fill_method=None`, and infinities are
converted to NaN — Tesla genuinely reported diluted EPS of 0.00 for the
quarter ending 2013-03-31, so the growth rate there is undefined rather than
erroneous.

---

## 2026-07-29 — Daily ETL split into stages; nightly failures fixed

**What was happening**: every scheduled DAG run failed from 2026-07-24 to
2026-07-28. Prices fell two trading days behind while news kept arriving, and
no alert reached anyone for five days.

**What made it undiagnosable**: the task ran `python -m src.etl.run_daily`
without `-u`. Python buffers stdout when it is a pipe, so when the process was
SIGTERMed the entire log was discarded unwritten — the failed runs left behind
one Hugging Face warning on stderr and nothing else, with no way to tell which
stage had even been reached. Measured against that, the runtime assumption in
the old comment ("a full 30-ticker run takes a few minutes") was never
checked. It is 52 seconds end to end.

**Structural fix**: `run_daily.py` now has three stages — `prices`, `news`,
`dq` — each committing its own transaction and running as its own Airflow
task, with `prices` and `news` in parallel and `dq` on `trigger_rule=all_done`
so the report still goes out on a failed night. Previously all of it shared
one transaction and one task, which coupled failures that have nothing to do
with each other: news needs FinBERT and 30 RSS feeds and is the slow, fragile
half, while prices are fast and reliable — and yet a stall in the former rolled
back the latter. The asymmetry matters because news cannot be refetched (Google
News RSS has no archive) while prices and technical indicators can always be
rebuilt from stored history.

**`smtplib` had no timeout** (`src/alerting.py`): `SMTP_SSL` blocks forever on
a socket that connects but never replies. That call sits at the very end of
the ETL, after everything is committed, so a hang there fails a run whose work
had already succeeded — and it is the alerting path itself, the thing meant to
report trouble. Now 30 seconds, with tests.

**Timeouts and retries**: per-stage timeouts sized against measured runtime
(15/20/10 minutes against 43s/2m36s/9s observed) instead of one 30-minute
budget for everything, and retries cut from 3 to 2 — every failure so far
repeated identically on retry, so extra attempts only delayed the alert.

**Verified**: manual run `p0_verify_1785301207` succeeded on all three tasks;
logs are now readable; the summary email sent. Prices, news, sentiment and
technical indicators are all current to 2026-07-29.

**Not established**: the original hang was never reproduced. Running each
stage by hand inside the worker container succeeded, the FinBERT model loads
in 6.3s there, and both huggingface.co and smtp.gmail.com are reachable from
it in under a second. The unbounded SMTP call is the best-supported
explanation — it would leave a committed database and a failed task, which is
what was observed — but it is not proven, which is precisely why the logging
fix matters more than the diagnosis.
