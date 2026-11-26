# References

Similar public projects reviewed before building, as checked on 2026-11-26. Licenses were checked on
each repo's GitHub page or through the GitHub API. Ideas we adapt are credited here and in code comments
where they are used. No code is copied verbatim.

| Repo | License | What we borrow | Why not fork (share of our scope) |
| --- | --- | --- | --- |
| [Pann13223029/merch-store-marketing-case-study](https://github.com/Pann13223029/merch-store-marketing-case-study) | MIT | Builds one row per session over `UNNEST(hits)` and counts funnel steps with `COUNTIF(eCommerceAction.action_type = ...)`. Revenue is `/1e6`, and purchases are flagged with `totals.transactions > 0`. Uses a session key of `fullVisitorId + visitId + visitStartTime` because visitId repeats across midnight. Flags internal or staff traffic once per visitor. Its pytest tests run on synthetic data, so CI needs no BigQuery. | Same dataset and dates, but its focus is attribution (including Markov) and retargeting. It has no cohort retention, no CAC or spend model and no static dashboard. About 30–35%. |
| [guiarpi/ga4-product-analytics](https://github.com/guiarpi/ga4-product-analytics) (formerly `guiarpi/funnel-analysis`) | MIT | Module split (`queries` / `metrics` / `charts` / dashboard generator) and Jinja2 + self-contained Plotly HTML on GitHub Pages. Cost guards: `maximum_bytes_billed`, dry runs, `_TABLE_SUFFIX` filters. Picks first-touch values with `ARRAY_AGG(... IGNORE NULLS ORDER BY ts LIMIT 1)`. Leaves cohort cells blank when the period hasn't finished. | It uses the GA4 sample (event_params schema and about 3 months of data), so it is too short for 90-day retention and none of its SQL carries over. It has no CAC or ROI. About 40% by structure, about 0% of reusable SQL. |
| [AIVIETNAM-AIO-Tranthanhdat/ga360-sql-playbook](https://github.com/AIVIETNAM-AIO-Tranthanhdat/ga360-sql-playbook) | MIT | Reference patterns for this exact schema: `action_type` codes, `/1e6` scaling, `UNNEST(hits)` / `UNNEST(product)`, `SAFE_DIVIDE`, window totals. | A single SQL file. It has no channel funnel, cohorts, CAC, Python, tests or dashboard. About 10–15%. |

## Fork or build decision

**Build fresh.** No repo covers more than half of the scope. The closest one on the same dataset
covers about a third and has no retention, spend model or dashboard. The closest one in stack uses the
GA4 schema, so its SQL would all need rewriting. Forking would also label the repo "forked from …" and
keep its commits off the owner's contribution graph.

## Considered and rejected

- [akprodromou/Google-Analytics-User-Analysis](https://github.com/akprodromou/Google-Analytics-User-Analysis): no license, a single-day notebook, no cohorts or CAC. Useful only as a schema walk-through.
- [fmgarate/bq-ga360](https://github.com/fmgarate/bq-ga360): no license, last updated 2019, queries for a private GA360 property.
- [20preetika/Acquisition-funnel-bigquery-analysis](https://github.com/20preetika/Acquisition-funnel-bigquery-analysis): no license, channel funnel step counts for Aug 2017 only.
- [Wilsbert12/google-merch-store-eda](https://github.com/Wilsbert12/google-merch-store-eda): MIT, exploratory notebook, no funnel, cohort or CAC work.
- [fserrey/google-analytics-sql](https://github.com/fserrey/google-analytics-sql): listed as Apache-2.0 (license file not opened), basic e-commerce KPI scripts, last updated 2021.

## Datasets

- **Used:** `bigquery-public-data.google_analytics_sample.ga_sessions_*` (Google Merchandise Store, GA360, 2016-08-01 to 2017-08-01).
- **Rejected:** REES46 e-commerce behaviour data (Kaggle). It has no traffic source, channel or campaign column, so it cannot attribute acquisition.
