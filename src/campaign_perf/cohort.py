"""Assemble the user-level acquisition cohort from the parquet extracts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from campaign_perf.config import PROCESSED_DIR


def flag_internal(users: pd.DataFrame, rules: list[dict]) -> pd.Series:
    """True for users whose acquiring session matches any internal-traffic rule."""
    flag = pd.Series(False, index=users.index)
    for rule in rules:
        match = pd.Series(True, index=users.index)
        for col, value in rule.items():
            match &= users[col] == value
        flag |= match
    return flag


def load_cohort(cfg: dict, processed_dir: Path = PROCESSED_DIR) -> pd.DataFrame:
    """One row per acquired user with milestones, activity and 0-90 day revenue.

    Adds `internal` (staff traffic) and drops those users when internal_traffic.exclude is true.
    """
    users = pd.read_parquet(processed_dir / "user_first_touch.parquet")
    users = users[users["acquired"]].copy()
    users["internal"] = flag_internal(users, cfg["internal_traffic"]["rules"])

    for name in ("user_milestones", "user_activity_days", "cohort_revenue"):
        users = users.merge(
            pd.read_parquet(processed_dir / f"{name}.parquet"), on="fullVisitorId", how="left"
        )
    rev_cols = [c for c in users.columns if c.startswith(("revenue_d", "transactions_d"))]
    rev_cols.append("purchase_sessions_d0_90")
    users[rev_cols] = users[rev_cols].fillna(0)

    if cfg["internal_traffic"]["exclude"]:
        users = users[~users["internal"]]
    return users.reset_index(drop=True)
