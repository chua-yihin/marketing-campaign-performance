-- Whole-window totals straight from the source, to reconcile the extracts against.
SELECT
  COUNT(*) AS sessions,
  COUNT(DISTINCT fullVisitorId) AS users,
  SUM(IFNULL(totals.transactions, 0)) AS transactions,
  SUM(IFNULL(totals.transactionRevenue, 0)) / 1e6 AS revenue_usd,
  COUNT(DISTINCT IF(visitNumber = 1, fullVisitorId, NULL)) AS users_with_first_visit
FROM `bigquery-public-data.google_analytics_sample.ga_sessions_*`
WHERE _TABLE_SUFFIX BETWEEN '{start_suffix}' AND '{end_suffix}'
