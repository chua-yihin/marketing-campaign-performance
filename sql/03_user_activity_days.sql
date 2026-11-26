-- Return activity per acquired user, in days since first visit (day 0 = first-visit date).
-- Retained at N  <=> first_return_day <= N  (any session on days 1..N).
-- Purchase-retained at N <=> first_purchase_return_day <= N (any transaction on days 1..N).
-- Censoring (first visit >= N days before the end date) is applied in Python.
WITH s AS (
  SELECT
    fullVisitorId,
    visitId,
    visitStartTime,
    visitNumber,
    PARSE_DATE('%Y%m%d', date) AS session_date,
    IFNULL(totals.transactions, 0) AS transactions
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
  SELECT s.fullVisitorId, DATE_DIFF(s.session_date, a.first_date, DAY) AS day, s.transactions
  FROM s JOIN acq AS a USING (fullVisitorId)
)
SELECT
  fullVisitorId,
  MIN(IF(day >= 1, day, NULL)) AS first_return_day,
  MIN(IF(day >= 1 AND transactions >= 1, day, NULL)) AS first_purchase_return_day,
  COUNT(DISTINCT IF(day BETWEEN 1 AND 90, day, NULL)) AS active_days_1_90
FROM d
GROUP BY fullVisitorId
