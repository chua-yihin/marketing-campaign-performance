"""Build reports/tables/*.csv from data/processed/*.parquet and config/assumptions.yaml.

Cohorts:
  * Funnel and economics use users acquired at least `revenue_window_days` before the end date,
    so every user has a full 90-day window for purchases and revenue.
  * Retention uses every acquired user, censored separately at each N (see retention.py).
"""

from __future__ import annotations

import pandas as pd

from campaign_perf.cohort import load_cohort
from campaign_perf.config import TABLES_DIR, load_config
from campaign_perf.economics import (
    economics_table,
    months_between,
    pick_cut_scale,
    reallocation_impact,
    user_spend,
)
from campaign_perf.funnel import funnel_table
from campaign_perf.retention import retention_table

TOP_CAMPAIGNS = 10


def full_window_cohort(users: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, float]:
    """Users with a full revenue window, and the length of their acquisition window in months."""
    start = pd.Timestamp(cfg["data"]["start_date"])
    end = pd.Timestamp(cfg["data"]["end_date"])
    last_first_date = end - pd.Timedelta(days=cfg["economics"]["revenue_window_days"])
    cohort = users[pd.to_datetime(users["first_date"]) <= last_first_date].reset_index(drop=True)
    return cohort, months_between(start, last_first_date)


def channel_economics(users: pd.DataFrame, cfg: dict, months: float, multiplier=1.0):
    econ_cfg = cfg["economics"]
    rankable = {name for name, ch in cfg["channels"].items() if ch.get("rank", False)}
    spend = user_spend(users, cfg["channels"], months, multiplier)
    return economics_table(
        users,
        spend,
        "channel",
        econ_cfg["revenue_window_days"],
        econ_cfg["gross_margin"],
        rankable,
        econ_cfg["min_purchasers_to_rank"],
    )


def sensitivity(users: pd.DataFrame, cfg: dict, months: float, base_cut: str, base_scale: str):
    """Uniform x0.5/x1/x1.5 on every channel, plus one-channel-at-a-time x0.5/x1.5."""
    rows, picks = [], []
    for m in cfg["economics"]["sensitivity_multipliers"]:
        econ = channel_economics(users, cfg, months, m)
        cut, scale = pick_cut_scale(econ)
        picks.append({"scenario": f"all channels x{m}", "cut": cut, "scale": scale})
        part = econ[["channel", "spend", "cac", "roi_90d", "ranked"]].copy()
        part.insert(0, "multiplier", m)
        rows.append(part)

    ranked = channel_economics(users, cfg, months).query("ranked")["channel"].tolist()
    for ch in ranked:
        for m in cfg["economics"]["sensitivity_multipliers"]:
            if m == 1.0:
                continue
            econ = channel_economics(users, cfg, months, {ch: m})
            cut, scale = pick_cut_scale(econ)
            picks.append({"scenario": f"{ch} only x{m}", "cut": cut, "scale": scale})

    summary = pd.DataFrame(picks)
    summary["same_cut"] = summary["cut"] == base_cut
    summary["same_scale"] = summary["scale"] == base_scale
    summary["recommendation_holds"] = summary["same_cut"] & summary["same_scale"]
    return pd.concat(rows, ignore_index=True), summary


def main() -> None:
    cfg = load_config()
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    end = pd.Timestamp(cfg["data"]["end_date"])
    window = cfg["economics"]["revenue_window_days"]
    repeat_window = cfg["funnel"]["repeat_window_days"]
    margin = cfg["economics"]["gross_margin"]
    penalty = cfg["economics"]["scale_marginal_cac_penalty"]

    users = load_cohort(cfg)
    cohort, months = full_window_cohort(users, cfg)
    print(f"Acquired users: {len(users):,}; full 90-day cohort: {len(cohort):,} ({months:.2f} mo)")

    # Funnel, economics, retention by channel
    funnel = funnel_table(cohort, "channel", window, repeat_window, end)
    econ = channel_economics(cohort, cfg, months)
    retention = retention_table(users, "channel", cfg["retention"]["windows_days"], end)
    funnel.to_csv(TABLES_DIR / "funnel_by_channel.csv", index=False)
    econ.to_csv(TABLES_DIR / "economics_by_channel.csv", index=False)
    retention.to_csv(TABLES_DIR / "retention_by_channel.csv", index=False)

    # Same economics with internal staff traffic left in, to show its effect
    cfg_incl = {**cfg, "internal_traffic": {**cfg["internal_traffic"], "exclude": False}}
    cohort_incl, _ = full_window_cohort(load_cohort(cfg_incl), cfg)
    channel_economics(cohort_incl, cfg, months).to_csv(
        TABLES_DIR / "economics_by_channel_incl_internal.csv", index=False
    )

    # Cut / scale, reallocation impact and sensitivity
    cut, scale = pick_cut_scale(econ)
    sens_detail, sens_summary = sensitivity(cohort, cfg, months, cut, scale)
    sens_detail.to_csv(TABLES_DIR / "sensitivity.csv", index=False)
    sens_summary.to_csv(TABLES_DIR / "sensitivity_summary.csv", index=False)

    # Impact range: the cut channel's spend and the scale channel's spend (hence its CAC) move
    # in opposite directions, so the range reflects real uncertainty in the assumptions.
    lo_m, _, hi_m = sorted(cfg["economics"]["sensitivity_multipliers"])
    scenarios = {
        "low": {cut: lo_m, scale: hi_m},
        "base": {},
        "high": {cut: hi_m, scale: lo_m},
    }
    impacts = []
    for name, mult in scenarios.items():
        e = channel_economics(cohort, cfg, months, mult)
        impact = reallocation_impact(
            e, cut, scale, margin, penalty, cfg["economics"]["scale_max_multiple"]
        )
        impacts.append(
            {
                "scenario": name,
                "cut_spend_multiplier": mult.get(cut, 1.0),
                "scale_spend_multiplier": mult.get(scale, 1.0),
                **impact,
            }
        )
    pd.DataFrame(impacts).to_csv(TABLES_DIR / "reallocation_impact.csv", index=False)

    # Top campaigns by new users (full-window cohort for funnel/economics)
    top = cohort["campaign"].value_counts().head(TOP_CAMPAIGNS).index
    camp = cohort[cohort["campaign"].isin(top)]
    camp_users = users[users["campaign"].isin(top)]
    spend = user_spend(cohort, cfg["channels"], months)
    funnel_table(camp, "campaign", window, repeat_window, end, "All top campaigns").to_csv(
        TABLES_DIR / "funnel_by_campaign.csv", index=False
    )
    economics_table(camp, spend[camp.index], "campaign", window, margin).sort_values(
        "new_users", ascending=False
    ).to_csv(TABLES_DIR / "economics_by_campaign.csv", index=False)
    retention_table(
        camp_users, "campaign", cfg["retention"]["windows_days"], end, "All top campaigns"
    ).to_csv(TABLES_DIR / "retention_by_campaign.csv", index=False)

    print(f"Cut: {cut} | Scale: {scale}")
    print(
        f"Recommendation holds in {sens_summary['recommendation_holds'].sum()}"
        f" of {len(sens_summary)} sensitivity scenarios"
    )
    print(f"Tables written to {TABLES_DIR}")


if __name__ == "__main__":
    main()
