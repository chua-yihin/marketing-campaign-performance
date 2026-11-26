# Methodology

Definitions follow [CLAUDE.md](../CLAUDE.md). Every parameter is set in
[config/assumptions.yaml](../config/assumptions.yaml).

## Data and extraction
- Source: `bigquery-public-data.google_analytics_sample.ga_sessions_*`, 2016-08-01 to 2017-08-01
  (903,653 sessions, 714,167 users, 12,115 transactions, $1,540,071 revenue).
- `sql/01`–`04` produce user-level extracts in `data/processed/`. `sql/05` gives source totals.
  Sessions, users, transactions and revenue rebuilt from the extracts match the source exactly
  (`reports/tables/reconciliation.csv`). The full extraction processes about 0.4 GB.
- **Acquired users:** 701,500 of the 714,167 users have `visitNumber = 1` on their first session in
  the window. The other 12,667 were acquired before August 2016 and are excluded from the cohorts.
- Days are counted from the first-visit date (`date` field, property time zone). Day 0 is the
  first-visit date.

## Sign-up definition
The sample has no sign-up event. A probe (`sql/00_signup_probe.sql`, output
`reports/tables/signup_probe.csv`) found these registration-like pages:

| Page | Users | Share of all users |
| --- | --- | --- |
| /registersuccess.html | 15,902 | 2.2% |
| /register.html | 4,438 | 0.6% |
| /guestregister.html | 386 | 0.05% |
| (any add-to-cart, for comparison) | 39,817 | 5.6% |

`/registersuccess.html` is above the 1% threshold, so **sign-up = first session with a hit on
`/registersuccess.html`**.

Caveats:
- About 3.6 times as many users reach the success page as reach the registration form, so the page
  probably also fires on login or a redirect. Treat the stage as "registered or logged in".
- The store allows guest checkout. 4,768 of 9,063 purchasing users (53%) never hit the page, so
  sign-up is not a gate before purchase.

## Funnel structure
Because of guest checkout, the funnel is reported in two ways:
- **Nested funnel (for step conversion):** visit → sign-up → first purchase *among sign-ups* →
  repeat purchase within 90 days *among those purchasers*. Each step rate has a Wilson 95% CI.
- **All purchasers (for economics):** CAC, ROI and LTV:CAC use every first-time purchaser, signed
  up or not.

## Internal (staff) traffic
In this sample, Referral traffic with source `(direct)` / medium `(none)` is Google's own internal
traffic. Users acquired this way:

| | Users | Purchasers | Purchase rate |
| --- | --- | --- | --- |
| Referral, source `(direct)` | 30,394 | 3,347 | 11.0% |
| All other Referral sources | 22,699 | 80 | 0.35% |

These 30,394 users are excluded from all cohorts (`internal_traffic` in `config/assumptions.yaml`),
which leaves 671,106 acquired users. Results with them included are reported alongside, so the
effect is visible. The rule flags the acquiring session only. Staff who first arrived through
another channel cannot be identified.
