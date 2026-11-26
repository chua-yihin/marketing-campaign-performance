# Definitions and conventions: marketing-campaign-performance

End-to-end campaign performance analysis of the Google Analytics 360 sample in BigQuery:
funnel by acquiring channel, CAC and ROI under assumed spend, 30/60/90-day retention, a
one-page cut/scale memo and a static dashboard. These definitions are fixed; change them only
with the owner's agreement, and update `docs/methodology.md` and this file in the same commit.

## Data
- Source: `bigquery-public-data.google_analytics_sample.ga_sessions_*`, suffixes 20160801..20170801.
- Billing project and every other parameter: `config/assumptions.yaml`.
- REES46 (Kaggle) was considered and rejected: no channel, source or campaign column.

## Definitions
- **Acquisition**: a user's (`fullVisitorId`) first session, `visitNumber = 1`. Its `channelGrouping`
  is the acquiring channel (first-touch). Keep `trafficSource.campaign` for a campaign cut.
  Users whose first session in the data has `visitNumber > 1` were acquired before the window and
  are excluded from acquisition cohorts.
- **Internal traffic**: users acquired via Referral with source "(direct)" / medium "(none)" are
  Google staff traffic and are excluded (config `internal_traffic`); report results with them too.
- **Funnel shape**: guest checkout means sign-up is not a gate. Step conversion uses a nested funnel
  (purchase among sign-ups); economics use all first-time purchasers.
- **Sign-up**: no sign-up event exists. Chosen by probe (see `funnel.signup_definition`):
  registration-success page if >= 1% of users hit it, else first add-to-cart
  (`hits.eCommerceAction.action_type = '3'`), labelled "Engaged (add to cart)".
- **First purchase**: first session with `totals.transactions >= 1`.
- **Revenue**: `totals.transactionRevenue / 1e6` (USD). Never forget the 1e6.
- **Repeat purchase**: a second transaction session within 90 days of the first.
- **Retention at N** (30/60/90): any session on days 1..N after first visit. Purchase retention:
  any transaction on days 1..N. Right-censoring: only users whose first visit is >= N days before
  2017-08-01.
- **Economics**: step conversion = stage n / stage n-1; CAC = spend / first-time purchasers;
  cost per new user = spend / new users; 90-day revenue per acquired user = days 0..90 cohort
  revenue / new users; ROI = (90-day revenue x margin - spend) / spend; LTV:CAC = 90-day gross
  profit per purchaser / CAC.
- **Uncertainty**: Wilson 95% CIs on every conversion and retention rate. Channels with < 30
  first-time purchasers are flagged and not ranked. Direct and (Other) are never ranked.
- **Sensitivity**: every channel's spend at x0.5, x1.0, x1.5; report whether cut/scale survives.

## Conventions
- All assumptions in `config/assumptions.yaml`, never in code.
- BigQuery: dry run first, print bytes, refuse > 20 GB, set `maximum_bytes_billed`, select only
  needed columns, always filter `_TABLE_SUFFIX`. Heavy aggregation in SQL.
- Extracts go to `data/processed/*.parquet` (committed, each < 50 MB) so the repo reruns without GCP.
- Analysis modules (`funnel`, `economics`, `retention`) are pure functions over DataFrames, tested
  with tiny hand-built fixtures in `tests/`.
- Every number in `reports/memo.md`, the README headline and the dashboard is read from
  `reports/tables/*.csv` by `report.py`. Never type a result number by hand.
- Chart titles state the finding, not the topic. One palette, defined once in `charts.py`.
- Environment: uv, Python 3.11+, versions pinned in `pyproject.toml`. Lint with ruff.
- Never commit credentials, `.env` or key files. Auth is ADC (`gcloud auth application-default login`).
- Commands: `make extract` (needs GCP) | `make analyze` | `make report` | `make test` | `make all`
  (`all` = analyze + report + test, runs from committed parquet without GCP).
