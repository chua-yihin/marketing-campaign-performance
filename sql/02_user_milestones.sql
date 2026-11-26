-- Funnel milestones per acquired user, as days since first visit (day 0 = first-visit date).
--   signup_day:          first session with a hit on /registersuccess.html (probe: 2.2% of users)
--   first_purchase_day:  first session with totals.transactions >= 1
--   second_purchase_day: second such session (repeat = within 90 days of the first, in Python)
WITH s AS (
  SELECT
    fullVisitorId,
    visitId,
    visitStartTime,
    visitNumber,
    PARSE_DATE('%Y%m%d', date) AS session_date,
    channelGrouping,
    IFNULL(totals.transactions, 0) AS transactions,
    IFNULL(totals.transactionRevenue, 0) / 1e6 AS revenue_usd,
    EXISTS(
      SELECT 1 FROM UNNEST(hits) AS h
      WHERE LOWER(h.page.pagePath) LIKE '/registersuccess.html%'
    ) AS has_signup
  FROM `bigquery-public-data.google_analytics_sample.ga_sessions_*`
  WHERE _TABLE_SUFFIX BETWEEN '{start_suffix}' AND '{end_suffix}'
),
first_s AS (
  SELECT
    fullVisitorId,
    ARRAY_AGG(STRUCT(visitNumber, session_date) ORDER BY visitStartTime, visitId LIMIT 1)
      [OFFSET(0)] AS f
  FROM s
  GROUP BY fullVisitorId
),
acq AS (
  SELECT fullVisitorId, f.session_date AS first_date FROM first_s WHERE f.visitNumber = 1
),
purchases AS (
  SELECT
    fullVisitorId,
    ARRAY_AGG(
      STRUCT(session_date, revenue_usd, channelGrouping) ORDER BY visitStartTime, visitId LIMIT 2
    ) AS p
  FROM s
  WHERE transactions >= 1
  GROUP BY fullVisitorId
),
signups AS (
  SELECT fullVisitorId, MIN(session_date) AS signup_date
  FROM s
  WHERE has_signup
  GROUP BY fullVisitorId
)
SELECT
  a.fullVisitorId,
  DATE_DIFF(su.signup_date, a.first_date, DAY) AS signup_day,
  DATE_DIFF(p.p[SAFE_OFFSET(0)].session_date, a.first_date, DAY) AS first_purchase_day,
  p.p[SAFE_OFFSET(0)].revenue_usd AS first_purchase_revenue_usd,
  p.p[SAFE_OFFSET(0)].channelGrouping AS first_purchase_channel,
  DATE_DIFF(p.p[SAFE_OFFSET(1)].session_date, a.first_date, DAY) AS second_purchase_day
FROM acq AS a
LEFT JOIN signups AS su USING (fullVisitorId)
LEFT JOIN purchases AS p USING (fullVisitorId)
