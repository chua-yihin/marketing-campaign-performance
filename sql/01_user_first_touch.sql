-- One row per user (fullVisitorId) seen in the window.
-- Acquisition = the user's first session in the window, if it has visitNumber = 1.
-- Users whose first session in the window has visitNumber > 1 were acquired before the
-- data starts: kept for reconciliation, excluded from acquisition cohorts (acquired = FALSE).
-- Also carries each user's whole-window totals so the extract reconciles with 05_validation.
-- First-touch via ARRAY_AGG(... ORDER BY ... LIMIT 1): pattern credited in docs/references.md.
WITH s AS (
  SELECT
    fullVisitorId,
    visitId,
    visitStartTime,
    visitNumber,
    PARSE_DATE('%Y%m%d', date) AS session_date,
    channelGrouping,
    trafficSource.source AS source,
    trafficSource.medium AS medium,
    trafficSource.campaign AS campaign,
    IFNULL(totals.transactions, 0) AS transactions,
    IFNULL(totals.transactionRevenue, 0) / 1e6 AS revenue_usd
  FROM `bigquery-public-data.google_analytics_sample.ga_sessions_*`
  WHERE _TABLE_SUFFIX BETWEEN '{start_suffix}' AND '{end_suffix}'
)
SELECT
  fullVisitorId,
  f.visitNumber = 1 AS acquired,
  f.session_date AS first_date,
  f.channelGrouping AS channel,
  f.source,
  f.medium,
  f.campaign,
  n_sessions,
  n_transactions,
  revenue_usd
FROM (
  SELECT
    fullVisitorId,
    ARRAY_AGG(
      STRUCT(visitNumber, session_date, channelGrouping, source, medium, campaign)
      ORDER BY visitStartTime, visitId LIMIT 1
    )[OFFSET(0)] AS f,
    COUNT(*) AS n_sessions,
    SUM(transactions) AS n_transactions,
    SUM(revenue_usd) AS revenue_usd
  FROM s
  GROUP BY fullVisitorId
)
