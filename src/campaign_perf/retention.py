"""30/60/90-day retention with right-censoring.

Retained at N: any session on days 1..N after the first visit (first_return_day <= N).
Purchase-retained at N: any transaction on days 1..N (first_purchase_return_day <= N).
Only users whose first visit is at least N days before the end date are counted at N.
"""

from __future__ import annotations

import pandas as pd

from campaign_perf.stats import add_rate


def retention_table(
    users: pd.DataFrame,
    by: str,
    windows: list[int],
    end_date: pd.Timestamp,
    total_label: str = "All channels",
) -> pd.DataFrame:
    """Long table: one row per (group, N) with eligible users, retention and purchase retention."""
    first = pd.to_datetime(users["first_date"])
    frames = []
    for n in windows:
        eligible = (first <= end_date - pd.Timedelta(days=n)).to_numpy()
        returned = users["first_return_day"].le(n).fillna(False).to_numpy(dtype=bool)
        bought = users["first_purchase_return_day"].le(n).fillna(False).to_numpy(dtype=bool)
        df = pd.DataFrame(
            {
                by: users[by].to_numpy(),
                "eligible_users": eligible,
                "retained": eligible & returned,
                "purchase_retained": eligible & bought,
            }
        )
        g = df.groupby(by)[["eligible_users", "retained", "purchase_retained"]].sum()
        g.loc[total_label] = g.sum()
        g = g.astype(int)
        g.index.name = by
        g = g.reset_index()
        g.insert(1, "window_days", n)
        frames.append(g)
    out = pd.concat(frames, ignore_index=True)
    out = add_rate(out, "retention", "retained", "eligible_users")
    out = add_rate(out, "purchase_retention", "purchase_retained", "eligible_users")
    return out
