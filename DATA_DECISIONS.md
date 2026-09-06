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

**Why it matters**: only the scheduled daily run accumulates sentiment, so any
ticker missing from the Airflow list lost coverage for every day it stayed
missing. This — not the RSS query wording — is the main reason coverage was so
uneven: AAPL/MSFT/TSLA reached ~90 days while the other 23 tickers had almost
none until a few manual runs in July 2026.

**Correction (2026-09-05)**: this entry originally justified the above with
"News/sentiment cannot be backfilled (Google News RSS returns only current
headlines)." That is false — see the 2026-09-05 entry below. The days lost
here were recoverable and have since been recovered.

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
back the latter. (This paragraph originally added "because news cannot be
refetched (Google News RSS has no archive)"; that justification was wrong — see
2026-09-05 — but the split is still right on its own merits.)

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

---

## 2026-07-29 — Search terms fixed: 20/21 equities improved, most from near-zero

**What**: `TICKERS stock` (a single extra word) is now the default RSS search
term for 20 of 21 equities. NFLX keeps the bare ticker.

**Why this isn't the same mistake as before**: a 2026-07-25 entry in this file
documents removing natural-language overrides (e.g. AMZN -> "Amazon stock
e-commerce") because they measured worse than the bare ticker across the
board. That result was correct but got over-generalized in practice into
"bare ticker is the answer" — which happened to be true for AAPL/MSFT/AMZN/
TSLA/GOOGL (distinctive alphabetic strings that work as search terms on their
own) and silently wrong for tickers that collide with ordinary English or are
too short to mean anything to a full-text search: `V`, `BA`, `HD`, `KO`, `PG`,
`DIS` returned 0-2 trusted-source articles/week on the bare ticker because
"V" and "BA" aren't words and "HD"/"KO"/"PG" match unrelated content.

Re-measured properly this time — all 21 equities, bare vs `TICKER stock`,
trusted-source count over the same 168h window the pipeline actually uses —
appending "stock" won 20/21, several from zero: KO 0->10, HD 0->14, DIS 0->23,
BA 0->5, V 1->10, WMT 1->16, JNJ 1->13, INTC 1->13, JPM 4->18, XOM 9->32. It
also improved the tickers that were already fine (AAPL 18->39, AMZN 25->62),
so this is not "compensating for bad tickers" so much as "stock" being a
better query word than nothing. NFLX was the one loser (14->12) and was left
on the bare ticker.

**Verified with a live run**: 534 news items fetched (was 311-321), and the
previously-worst tickers now show real weekly volume: XOM 33, DIS 23, WMT 17,
HD 14, PG 14, JNJ 13, INTC 13, V 11, KO 10, BA 5. BA remains the thinnest —
Boeing coverage in the trusted-source list appears to be genuinely lighter —
but that is a real weekly count now, not zero.

**Same caveat as before applies**: Google News' ranking for a query drifts.
Re-measure with `search_term_experiment.py`-style live queries before changing
this again rather than assuming the current numbers hold indefinitely.

---

## 2026-09-05 — "News cannot be backfilled" was wrong; lookback 7d -> 90d

**The claim being retracted**: several entries above, plus comments in
`run_daily.py`, `backfill_price_history.py` and the DAG, stated that Google
News RSS "returns only current headlines" / "has no archive", so a day not
fetched was lost permanently. That was never measured. It is false.

**What the feed actually does**: one query returns ~100 entries reaching back
roughly 140 days. What discarded the older ones was our own `LOOKBACK_HOURS`
filter — applied client-side to entries already in hand, not a fetch parameter.
Measured across 10 tickers, trusted-source articles kept:

| window | articles |
|---|---|
| 168h (7d, old default) | 171 |
| 720h (30d) | 250 |
| 2160h (90d, new default) | 507 |

**Why it went unnoticed for so long**: the belief was self-confirming. With a
7-day filter every run only ever saw a week of news, so the data always looked
like a feed that only carries a week of news.

**Changed**: `LOOKBACK_HOURS` 168 -> 2160 in `src/config.py`, `.env`,
`.env.airflow`. Two supporting fixes were required for that to mean anything:

1. `stage_news` now dedupes by `news_hash` *before* FinBERT scoring. Without
   it, every night re-scores the whole 90-day back-catalogue; with it, cost is
   proportional to genuinely new articles (a catch-up run scored 857 of 1,329
   fetched, the next 331 of 1,308).
2. `stage_news` rebuilds the daily sentiment index across the whole lookback
   window rather than the last 7 days. Without this the widened fetch would
   have silently changed nothing user-visible: old articles reach `fact_news`
   but `fact_sentiment_daily` — what the model and dashboard read — would still
   only cover a week.

**Result of the catch-up run**: the 2026-08-14 → 09-05 gap (22 days, created by
the machine being powered off, not by any code failure) is filled — every day
in it now has news. Tickers with >= 30 days of sentiment, the threshold Track A
needs, went from **7/30 to 26/30**. `fact_news` 5,911 -> 7,099;
`fact_sentiment_daily` 991 -> 1,487.

Recovered days are thinner than live-fetched ones (5-28 articles/day vs
90-154), which is the ~100-entry cap showing through. Running daily still
matters; it just is not the difference between data and no data.

**Still under 30 days**: GC=F (29), EURUSD=X (19), ETH-USD (13), THBUSD=X (7) —
all non-equities whose natural-language search terms return few
trusted-source hits.

---

## 2026-09-05 — Unescaped '&' broke the ^GSPC search for months

**What**: both ETLs built the RSS URL with `search_q.replace(" ", "%20")`,
which escapes spaces and nothing else. The ^GSPC term is "S&P 500 stock market
index", so the raw `&` ended the `q=` parameter and Google received `q=S` —
^GSPC was searching for the letter S.

**Why it was invisible**: the malformed query still returned ~100 well-formed
entries, so the feed looked healthy. Only the kept-after-filtering count gave
it away (3 of 102). Percent-encoding the query takes it to 43, and ^GSPC over
the 30-day threshold.

Both call sites now use `google_news_rss_url()` in `src/extract/news_rss.py`,
covered by `tests/test_news_rss.py`.

---

## 2026-09-05 — Price fetching now closes its own gaps

**What**: `run_daily.stage_prices` chooses its lookback from the data instead
of always fetching 14 days. `choose_price_lookback()` widens the window to
reach whichever is further back: the stalest ticker's newest row, or the
oldest calendar date inside the stored range that has no price row at all.
Bounded to 14-400 days.

**Why**: the fixed 14-day window made outages permanent. The machine was off
2026-08-12 → 08-21; the next run's window began after the hole, so it filled
recent days, reported success, and left ten days that no later run could ever
reach — the window only moves forward. Prices are fully re-fetchable, so
losing them was avoidable.

**Two kinds of gap, and only checking the first is what let this survive**:

- *trailing* — newest stored day is behind today; caught by `max(d)`.
- *interior* — days missing in the middle with data on both sides, so `max(d)`
  is perfectly current and reports nothing wrong. This is the case that hid.

Interior gaps are detected as calendar dates inside the stored range with zero
price rows. That is unambiguous because the crypto tickers trade every day
including weekends — BTC-USD has rows for 3,693 of the 3,705 calendar days it
spans, and the 12 it lacked were exactly these outage days. A zero-row date is
therefore always a gap, never a market holiday.

**Repaired**: 2026-08-12 → 08-21 backfilled (and 2026-08-11, which had only 4
of 30 tickers). Zero-row dates in the last 400 days: none remaining.

A ticker newly added to `TICKERS` has no rows at all and pulls the full 400-day
window, so it starts with real history rather than a fortnight.

---

## 2026-09-05 — Why the pipeline stopped, and what now makes it self-healing

**The cause was never the code.** After the P0 fix (2026-07-29) every run
succeeded whenever the machine was on: 07-29, 07-30, 07-31 and 08-10 all
passed. The DAG history shows the real pattern — the run scheduled for 08-01
executed on 08-10, and the one scheduled for 08-11 executed on 09-03. Airflow
was catching up after outages of days to weeks. A laptop that is powered off
at 06:00 cannot run a nightly job.

**Two things made those outages lossy, and both are now fixed**:

1. News fetched a fixed 7-day window, so a catch-up run days later fetched
   nothing useful. Now 90 days (see the LOOKBACK_HOURS entry).
2. Prices fetched a fixed 14 days, so a catch-up run filled the recent end and
   left the middle permanently empty (see the price-lookback entry).

Together these mean a single run after an outage of up to ~90 days now
restores everything, so the pipeline no longer needs to run every day to avoid
losing data — it only needs to run.

**What actually broke the 2026-09-05 06:00 run** was smaller and more specific:
`fin-postgres` had restart policy `no` while every Airflow container had
`always`. Docker Desktop started, the whole Airflow stack came back on its own,
the DAG fired on schedule — against a database that was still stopped. Set to
`unless-stopped` in `docker-compose.yml` and applied to the running container.

**Also**: Docker Desktop had `AutoStart = False` and was not a login item, so
nothing ran until someone opened it by hand. Enabled both (macOS login item
plus Docker's own setting, kept in agreement so neither reverts the other).

**Still true**: an outage longer than ~90 days loses news beyond that window,
and recovered days are thinner than live-fetched ones. Running on a laptop
remains the weak link; a hosted scheduler would remove it entirely.

---

## 2026-09-05 — Non-equity search terms rewritten; coverage 7/30 -> 29/30

**What**: every non-equity search term in `src/config.py` was replaced, after
measuring candidates against the live feed. Trusted-source articles in the
90-day window, before -> after:

| ticker | old term | new term | before | after |
|---|---|---|---|---|
| GC=F | gold price USD futures | `gold` | 4 | 39 |
| CL=F | crude oil price futures WTI | `WTI crude` | 30 | 42 |
| EURUSD=X | euro dollar exchange rate | `EUR USD` | 5 | 52 |
| THBUSD=X | Thai baht USD exchange rate | `Thai baht` | 1 | 9 |
| BTC-USD | Bitcoin USD price crypto | `Bitcoin` | 16 | 37 |
| ETH-USD | Ethereum USD price crypto | `ETH crypto` | 13 | 38 |
| ^GSPC | S&P 500 stock market index | `S&P 500` | 44 | 56 |
| ^DJI | Dow Jones industrial average | `Dow Jones` | 52 | 59 |
| ^IXIC | NASDAQ stock market index | `Nasdaq` | 30 | 83 |

**Why they were bad**: they read as descriptions rather than names, and
" market" is appended to every query, so they over-narrowed Google News'
full-text match — the same failure the old equity overrides had.

**The rule is "canonical instrument name", not "shorter"**. CL=F is the
counterexample that establishes it: bare `crude oil` scored 15, *worse* than
the long original, while `WTI crude` scored 42.

**Ranked on distinct days, not article count**, since >= 30 *days* is what
eligibility measures. The two can disagree: bare `Ethereum` returned 23
articles across only 10 days, while `ETH crypto` gave 38 across 26.

**Relevance was verified, not assumed**, because a broad word could quietly
pull in noise. All 39 `gold` headlines were about bullion — none about gold
medals, Goldman or miners — and all 38 `ETH crypto` headlines name
ETH/Ethereum. The trusted-source filter does most of this work: within the
financial press, "gold" means the metal.

**What was deliberately NOT done**: the rejected publishers were inspected
first, to check whether the filter rather than the query was the constraint.
They were mostly rate-quote pages and low-quality aggregators — Bybit (24
entries of exchange-rate pages for THB alone), CurrencyNews.co.uk,
exchangerates.org.uk, TradingView, Coinpedia. Adding them would have raised
the counts by lowering the evidentiary standard, so the trusted list is
unchanged.

**Result**: tickers with >= 30 days of sentiment went from 7/30 (start of day)
to **29/30**. `fact_news` 5,911 -> 7,512.

**Accepted limitation — THBUSD=X (14 days)**: the only ticker still short, and
not for want of trying. Every variant tested (`Thai baht`, `baht`, `USDTHB`,
`baht dollar`, `Thailand currency`, `Thai baht dollar`) topped out at 8-9
distinct days, with Bangkok Post as effectively the sole recurring publisher.
USD/THB simply is not covered daily by the international financial press. This
is a property of the asset's news coverage, not a pipeline defect, and should
be stated as such — or THBUSD=X excluded from sentiment-based analysis.

---

## 2026-09-05 — Track A re-run on 29 tickers: the sentiment edge does not survive

Re-ran Track A after sentiment coverage went from 5 eligible tickers to 29.
This is the headline result for the thesis, and it is negative.

**The earlier positive result was small-sample noise.** On ~5 tickers
(2026-07-25) the pooled sentiment model scored 0.635 against a 0.558 baseline
with 1 of 3 walk-forward folds beating its own baseline. On 29 tickers it
scores **0.483 against a 0.590 baseline, 0/3 folds**. Six times the tickers,
and the edge is gone.

**Sentiment does not merely fail to help — it measurably hurts.** Accuracy
against a majority baseline is a weak test here (the market trended up, and
`class_weight="balanced"` deliberately pushes predictions away from the base
rate), so technical-only and technical+sentiment were compared on *identical
rows* using AUC, which is threshold-free:

| horizon | AUC technical | AUC +sentiment | delta |
|---|---|---|---|
| 1d | 0.489 | 0.471 | −0.019 |
| 5d | 0.527 | 0.514 | −0.013 |
| 21d | 0.736 | 0.722 | −0.015 |

Negative at every horizon, consistently — the signature of adding noise
features to a small sample, not of a signal being missed.

**The dominant effect is regime shift, not model quality.** The training
window has a 0.438 up-day rate and the test window 0.590; at h=21d it is 0.489
against 0.688. The model learned a falling market and was tested on a rising
one. With ~9 months of sentiment history there is no way to train across
regimes, and no amount of feature engineering fixes that.

**Row counts were overstating the evidence by ~16x.** The pooled test set is
524 rows but only **33 distinct market days** — rows from the same day across
29 tickers move together with the market, so the day count is much closer to
the effective sample size. `sentiment_signal()` now returns `n_train_days` /
`n_test_days` and the walk-forward folds carry `n_test_days`; the dashboard
quotes days rather than rows. Every fold is ~32-35 market days.

**Do not read the h=21d AUC of 0.736 as a finding.** Its test set is 269 rows
over 27 market days, pooled across 25 tickers — roughly 27 independent
observations. It is a lead worth revisiting once there is more history, not a
result.

**What this supports**: the committee's original objection — that the
correlation work was not usable — now has direct evidence behind it rather
than being taken on faith. Track A's honest conclusion is that daily news
sentiment, as captured here, carries no exploitable short-horizon directional
information at the sample sizes available, and the technical-only baseline
does not beat a majority rule either (78,528 rows, 30 tickers, ~10 years).

---

## 2026-09-05 — Track B review: two bugs invalidated the old numbers, and the corrected result is still null

Reviewing Track B found that its published figures could not be trusted for
two independent reasons. Both are fixed; the conclusion after fixing is
unchanged in direction and much stronger in evidence.

### Bug 1 — 39% of the panel was anchored to the wrong date

`_nearest_price_on_or_after()` used `searchsorted` with no bound, so any
announcement predating the price history silently returned the *first stored
day*. Price history began 2016-07-14 while EDGAR fundamentals reach back to
2007, so **445 of 1,134 rows paired 2007-2016 fundamentals with the forward
return measured from July 2016** — and, all sharing one anchor date, repeated
the same ~21 return values hundreds of times. Nothing raised; the panel looked
full and well-populated.

Symptom that exposed it: 27.7 rows per anchor quarter across 21 tickers, which
is arithmetically impossible for one row per ticker-quarter. Distinct anchor
quarters were 41 where ~76 were expected.

Fixed with a 7-day tolerance (weekends and holidays are the only legitimate
delay), covered by `tests/test_dataset_fundamentals.py`. Rather than drop the
445 rows, price history was backfilled to 2006-09-11 (`backfill_price_history
--years 20`, 78,528 -> 145,918 rows), which makes them real observations:
panel back to 1,134 rows, distinct anchor quarters 41 -> 69, max rows in a
single ticker-quarter 36 -> 9.

### Bug 2 — untreated ratio outliers

The ratio features are arithmetically correct and statistically ruinous when a
denominator approaches zero. Observed in this panel: **P/E of 10,545** (AMZN
2023Q1 — price 105 over about a cent of trailing EPS), EPS growth of **-144**,
debt/equity of **133** (AMD 2015, near-zero book equity). One such row in a
test split drove OLS to **R^2 = -34**.

Features are now winsorized at the 1st/99th percentile, with bounds taken from
the *training* set only — full-panel bounds would let the test period shape its
own preprocessing and defeat the chronological split. Test R^2 went from -5.5 /
-9.9 / -4.5 to **-0.045 / -0.117 / -0.064**.

### The corrected result: nothing survives

Pearson r is nearly as outlier-fragile as OLS, so Spearman is now reported
first, with Pearson alongside so the gap is visible. Where they disagree, the
Pearson figure is being carried by a handful of rows:

| feature @ horizon | Pearson | Spearman |
|---|---|---|
| revenue_growth_qoq @ 63d | **+0.254 \*\*\*** | +0.046 (ns) |
| revenue_growth_qoq @252d | **+0.237 \*\*\*** | +0.041 (ns) |
| net_margin @252d | **−0.228 \*\*\*** | −0.053 (\*) |
| margin_delta_qoq @126d | +0.229 \*\*\* | +0.109 \*\*\* |

Out-of-sample, no horizon beats a train-mean baseline, and walk-forward beats
it in only 1-2 of 5 folds — those "wins" being less-negative R^2, not positive.

**And the survivors do not survive the sample size either.** Nominal n treats
1,100 rows as independent observations. They are not: forward-return windows
overlap (a 252-day return sampled quarterly overlaps the next by ~4x) and
tickers within a quarter move together (mean pairwise rho of 0.13-0.17 across
21 tickers, a design effect of 4.2-5.3x). Effective n is roughly 228 / 131 / 51
rather than ~1,100:

| feature | rho | p (nominal) | p (effective n) |
|---|---|---|---|
| margin_delta_qoq @126d | +0.109 | 0.000 | **0.221** |
| margin_delta_qoq @ 63d | +0.067 | 0.027 | **0.319** |
| pe_ratio @252d | −0.072 | 0.030 | **0.648** |

With 18 tests run (6 features x 3 horizons), about one p<0.05 is expected by
chance alone.

**Conclusion for the thesis**: quarterly fundamentals, as measured here, show
no relationship to subsequent returns that survives outlier treatment,
out-of-sample validation, or an honest accounting of the sample size. This is
a defensible negative result, and it is now the second one — Track A reached
the same verdict for sentiment on the same day.

---

## 2026-09-05 — Volatility forecasting: the first positive result

Every result in this project so far has been null. This one is not, and the
reason is that it asks a different question of the same data.

**Why direction was the wrong target.** Measured across all 30 assets over
2006-2026: lag-1 autocorrelation of daily returns averages **-0.053** — no
signal, which is exactly what Track A reported. Over the same rows, 20-day
realised volatility autocorrelates at **+0.901** at a 5-day lag and **+0.504**
at 20 days, and the weakest of the 30 assets still scores +0.821 at 5 days.
Volatility clusters; direction does not. Track A was not a modelling failure,
it was a question the data cannot answer.

**The test is skill against persistence, not R^2.** Predicting volatility from
volatility scores well by construction, so a headline R^2 says nothing. The
benchmark is the free forecast — "next period's volatility equals the current
20-day reading" — which any practitioner has for nothing. `skill = 1 -
MSE(model)/MSE(persistence)`; positive means the model earns its existence.

**Results** (`src/models/forecast_volatility.py`, chronological hold-out):

| horizon | model R² | persistence R² | skill | median error (ann %) |
|---|---|---|---|---|
| 5 days | 0.534 | 0.408 | **+0.213** | 6.22 vs 7.70 |
| 21 days | 0.739 | 0.606 | **+0.339** | 4.67 vs 5.78 |

Walk-forward: **5 of 5 folds beat persistence at both horizons**, spanning
2010-2026 including the COVID crash and the 2022 bear market. Skill ranges
+0.153 to +0.224 (5d) and +0.180 to +0.349 (21d). Per asset: **29 of 30 beat
persistence**, median skill +0.324. The exception is THBUSD=X (-0.085).

In-sample vs test R^2 is 0.610/0.534 at 5 days and 0.749/0.739 at 21 days —
the second is essentially no overfitting gap.

**Checked before believing it.** The failure mode that would make this look
excellent and be worthless is a forward window that includes the current day.
The window expression was verified position by position against a hand
computation, and confirmed that a spike on day *t* appears only in the targets
of days before *t*, never in day *t*'s own. Locked down by
`tests/test_dataset_volatility.py`.

**The edge is not a re-fitted persistence.** Ablation at 21 days:

| features | test R² | skill |
|---|---|---|
| persistence (free) | 0.606 | — |
| all features | 0.739 | +0.339 |
| `log_vol_20` only | 0.641 | +0.089 |
| **everything except `log_vol_20`** | **0.739** | **+0.339** |
| own volatility at 5/20/60 only | 0.708 | +0.260 |

Removing the persistence anchor entirely changes nothing, so the model is not
copying it. The value comes from volatility at several horizons at once, which
carries whether volatility is rising or falling and how far it sits from its
slower level — a mechanism that can be stated, not just fitted.

**A negative finding inside the positive one.** The two market-wide features
add nothing: dropping both moves the 21-day test R^2 from 0.739 to 0.740.
Recorded in the code so they are never cited as contributing.

**Caveats that belong in the write-up.** Forward windows on consecutive days
overlap heavily (a 5-day window shares 4 days with the next), so the effective
sample is far smaller than 143,947 rows — though this affects the model and
persistence identically, so the *comparison* stands. Rows also cluster
cross-sectionally across 30 assets on the same dates, as in Track B.

**Why this matters for the thesis.** It changes the conclusion from "nothing
in this data is predictable" to the more precise and more defensible "the
direction of returns is not predictable, their magnitude is" — and the
dashboard can say something useful and true.

---

## 2026-09-05 — Volatility forecast on the Signal tab, and a stale-asset bug

**What**: the Signal tab now leads with a volatility outlook — current 20-day
annualised volatility, forecasts for the next 5 and 21 trading days with a
band, and the ratio to current so "calmer" or "rougher" is readable at a
glance. Below it sits the evidence table: model R², the free forecast's R²,
skill, and typical error in annualised percent.

It is placed above the direction model deliberately. It is the one panel that
beats its baseline, and burying it under a model that does not would misstate
which part of this work is usable.

**Two fits per horizon, on purpose**: the accuracy claim comes from a model
trained on the chronological training window and scored on the held-out
remainder, while the number the user reads comes from a model refitted on all
history. Quoting out-of-sample skill next to an all-data prediction is the
honest pairing — the claim is earned on unseen data, the forecast is not
handicapped by ignoring recent years.

**Bug found while verifying the Thai translation** (`web/main.py`,
`_static_version`): the cache-busting token was computed from `style.css`'s
mtime alone, but the template appends it to `i18n.js` as well. Editing a
translation left the URL unchanged, so browsers kept serving the cached
`i18n.js` and new Thai strings silently never appeared — indistinguishable
from a broken translation. Every earlier i18n change only became visible
because some CSS edit happened to move the token. Now the newest mtime across
the whole static directory.

---

## 2026-09-06 — Company tab: what each business actually does, from its own filings

**What**: a new tab showing, per ticker, the SEC registrant profile (legal
name, SIC industry classification, state of incorporation, fiscal year end,
exchanges, filer category, headquarters, former names) and the Item 1
"Business" narrative from the most recent Form 10-K, plus the last eight
filings with direct links to sec.gov. Stored in `dim_company_profile`, loaded
by `src/scripts/load_company_profiles.py`, extracted by
`src/extract/company_profile_edgar.py`.

**Why EDGAR rather than a company-description API or an encyclopedia**: every
sentence shown is traceable to a specific document with an accession number
and a permanent SEC URL, and it is the company's own statutory account of its
operations, filed under legal obligation. A claim about what Apple does cites
Apple's 10-K, not a third party's summary of it. That is the difference
between a dashboard field and a citable source.

**Extraction succeeds for 19 of 21 equities; the 2 failures are structural,
not parsing bugs.**

| Ticker | Why it fails |
|---|---|
| MSFT | "Item 1. Business" occurs exactly once in the whole document — in the index. The body heading is formatted differently. |
| INTC | Uses a "Form 10-K Cross-Reference Index" mapping items to page numbers, so no Item 1 heading exists in the body at all. |

No regex fixes these, because the string being searched for is genuinely
absent. Those two store NULL and the page says so, still linking the filing.
A fragment that looks like a business description and is not would be worse
than none — the same reasoning that left Q4 derivation off.

**A start must pair with the FIRST following end.** The first heuristic paired
every "Item 1. Business" with every "Item 1A. Risk Factors" and took the
longest span, so a table-of-contents line paired with the last risk-factors
mention and swallowed the document: Coca-Cola came out at 214,481 characters.
Pairing each start with the first end that follows it, then taking the longest
such span, gives 92,190 for KO and a genuine 5,608–92,843 range across the 19.
Bounds of 3,000 and 150,000 characters reject the two remaining shapes of
mis-parse. Regression tests cover both, in `tests/test_company_profile_edgar.py`.

**A real bug found on the way in** (`src/extract/fundamentals_edgar.py`):
`www.sec.gov` returns 403 for any User-Agent with no email address in it,
whatever else the string says — measured across four variants. `data.sec.gov`
does not enforce this. The project's default UA had no email, so every
`www.sec.gov` request failed while `data.sec.gov` kept working. That is why
the fundamentals loader appeared healthy: it reads companyfacts from
`data.sec.gov` and only touches `www.sec.gov` for the CIK map, which it
silently fell back from. Set `SEC_USER_AGENT` to a real contact address; the
default is now only a format-satisfying placeholder.

**Nine of the 30 assets have no row at all** — BTC-USD, ETH-USD, ^GSPC, ^DJI,
^IXIC, GC=F, CL=F, EURUSD=X, THBUSD=X. Indices, forex, commodities and crypto
do not file with the SEC. The tab says this explicitly rather than showing an
empty profile, because "no registrant" is a property of the asset, not a gap
in the data.

**Paragraph breaks are rebuilt, wording is not touched.** Stripping markup
collapses whitespace, so the filing's own paragraph structure is gone before
the text reaches the database. The page regroups it every four sentences for
readability and says so on screen; no word is added, removed or reordered.
