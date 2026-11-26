-- Revenue per acquired user in days 0..30 / 0..60 / 0..90 after first visit (USD, /1e6).
-- Only users with at least one transaction session are returned; others have zero revenue.
WITH s AS (
  SELECT
    fullVisitorId,
    visitId,
    visitStartTime,
    visitNumber,
    PARSE_DATE('%Y%m%d', date) AS session_date,
    IFNULL(totals.transactions, 0) AS transactions,
    IFNULL(totals.transactionRevenue, 0) / 1e6 AS revenue_usd
  FROM `bigquery-public-data.google_analytics_sample.ga_sessions_*`
  WHERE _TABLE_SUFFIX BETWEEN '{start_suffix}' AND '{end_suffix}'
),
acq AS (
  SELECT fullVisitorId, f.session_date AS first_date
  FROM (
    SELECT
      fullVisitorId,
      ARRAY_AGG(STRUCT(visitNumber, session_date) ORDER BY visitStartTime, visitId LIMIT 1)
        [OFFSET(0)] AS f
    FROM s
    GROUP BY fullVisitorId
  )
  WHERE f.visitNumber = 1
),
d AS (
  SELECT
    s.fullVisitorId,
    DATE_DIFF(s.session_date, a.first_date, DAY) AS day,
    s.transactions,
    s.revenue_usd
  FROM s JOIN acq AS a USING (fullVisitorId)
  WHERE s.transactions >= 1 OR s.revenue_usd > 0
)
SELECT
  fullVisitorId,
  SUM(IF(day <= 30, revenue_usd, 0)) AS revenue_d0_30,
  SUM(IF(day <= 60, revenue_usd, 0)) AS revenue_d0_60,
  SUM(IF(day <= 90, revenue_usd, 0)) AS revenue_d0_90,
  SUM(IF(day <= 90, transactions, 0)) AS transactions_d0_90,
  COUNTIF(day <= 90 AND transactions >= 1) AS purchase_sessions_d0_90
FROM d
GROUP BY fullVisitorId
