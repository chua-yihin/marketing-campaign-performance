"""Funnel stage counts and step conversion with Wilson CIs.

Input: one row per acquired user (see cohort.load_cohort), restricted to users with a full
observation window. Stages are counted within `window` days of the first visit:
  visit -> sign-up -> first purchase among sign-ups -> repeat purchase among purchasers.
All first-time purchasers (signed up or not) are also reported, because guest checkout means
sign-up is not a gate.
"""

from __future__ import annotations

import pandas as pd

from campaign_perf.stats import add_rate


def user_stage_flags(
    users: pd.DataFrame, window: int, repeat_window: int, end_date: pd.Timestamp
) -> pd.DataFrame:
    """Per-user booleans for each funnel stage."""
    signup = users["signup_day"].le(window).fillna(False).astype(bool)
    purchase = users["first_purchase_day"].le(window).fillna(False).astype(bool)
    first_purchase_date = pd.to_datetime(users["first_date"]) + pd.to_timedelta(
        users["first_purchase_day"].astype(float), unit="D"
    )
    # Repeat is observable only if the first purchase has `repeat_window` days of data after it.
    repeat_eligible = purchase & (
        first_purchase_date <= end_date - pd.Timedelta(days=repeat_window)
    ).fillna(False)
    gap = users["second_purchase_day"].astype(float) - users["first_purchase_day"].astype(float)
    return pd.DataFrame(
        {
            "visit": True,
            "signup": signup,
            "purchase_after_signup": signup & purchase,
            "purchase": purchase,
            "repeat_eligible": repeat_eligible,
            "repeat": repeat_eligible & gap.le(repeat_window).fillna(False).astype(bool),
        },
        index=users.index,
    )


def funnel_table(
    users: pd.DataFrame,
    by: str,
    window: int,
    repeat_window: int,
    end_date: pd.Timestamp,
    total_label: str = "All channels",
) -> pd.DataFrame:
    """Stage counts and step conversion (Wilson 95% CIs) per value of `by`, plus a total row."""
    flags = user_stage_flags(users, window, repeat_window, end_date)
    flags[by] = users[by].to_numpy()
    g = flags.groupby(by).sum(numeric_only=True)
    g = g.rename(
        columns={
            "visit": "new_users",
            "signup": "signups",
            "purchase_after_signup": "purchasers_after_signup",
            "purchase": "purchasers",
            "repeat_eligible": "purchasers_repeat_eligible",
            "repeat": "repeat_purchasers",
        }
    ).astype(int)
    g.loc[total_label] = g.sum()
    g = add_rate(g, "signup_rate", "signups", "new_users")
    g = add_rate(g, "signup_to_purchase", "purchasers_after_signup", "signups")
    g = add_rate(g, "purchase_rate", "purchasers", "new_users")
    g = add_rate(g, "repeat_rate", "repeat_purchasers", "purchasers_repeat_eligible")
    g.index.name = by
    return g.reset_index()
