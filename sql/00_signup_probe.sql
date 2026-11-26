-- Sign-up probe: the GA sample has no sign-up event. How many users ever hit a
-- registration-like page? Compare with all users and with add-to-cart users.
WITH hits AS (
  SELECT
    fullVisitorId,
    LOWER(h.page.pagePath) AS path,
    h.eCommerceAction.action_type AS action_type
  FROM `bigquery-public-data.google_analytics_sample.ga_sessions_*`,
    UNNEST(hits) AS h
  WHERE _TABLE_SUFFIX BETWEEN '{start_suffix}' AND '{end_suffix}'
),
totals AS (
  SELECT
    COUNT(DISTINCT fullVisitorId) AS all_users,
    COUNT(DISTINCT IF(action_type = '3', fullVisitorId, NULL)) AS add_to_cart_users
  FROM hits
)
SELECT
  REGEXP_REPLACE(path, r'\?.*$', '') AS page_path,
  COUNT(DISTINCT fullVisitorId) AS users,
  ANY_VALUE(t.all_users) AS all_users,
  ANY_VALUE(t.add_to_cart_users) AS add_to_cart_users
FROM hits CROSS JOIN totals AS t
WHERE path LIKE '%regist%' OR path LIKE '%signup%' OR path LIKE '%sign-up%'
   OR path LIKE '%createaccount%' OR path LIKE '%create-account%'
GROUP BY page_path
ORDER BY users DESC
