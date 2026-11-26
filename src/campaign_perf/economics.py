"""Spend model, CAC, ROI, LTV:CAC, sensitivity and the cut/scale reallocation.

Spend is ASSUMED (the sample has no cost data); every number comes from config/assumptions.yaml.
Spend is assigned per user so any grouping (channel, campaign) sums correctly:
  per_session:    cost_per_session for each new user (one acquiring session each)
  revenue_share:  revenue_share x the user's 0-90 day revenue + cost_per_session
  fixed_monthly:  monthly_cost x months in the cohort window, split evenly over the channel's users
  none:           0
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DAYS_PER_MONTH = 365.25 / 12


def months_between(start: pd.Timestamp, end: pd.Timestamp) -> float:
    """Length of the acquisition window [start, end] in months, both days included."""
    return ((end - start).days + 1) / DAYS_PER_MONTH


def user_spend(
    users: pd.DataFrame,
    channels_cfg: dict,
    months: float,
    multiplier: float | dict[str, float] = 1.0,
) -> pd.Series:
    """Assumed acquisition spend attributed to each user.

    `multiplier` scales spend: one number for every channel, or {channel: multiplier}.
    """
    spend = pd.Series(0.0, index=users.index)
    counts = users["channel"].value_counts()
    for name, ch in channels_cfg.items():
        mask = (users["channel"] == name).to_numpy()
        if not mask.any():
            continue
        m = multiplier.get(name, 1.0) if isinstance(multiplier, dict) else multiplier
        model = ch["model"]
        if model == "per_session":
            s = np.full(mask.sum(), float(ch["cost_per_session"]))
        elif model == "revenue_share":
            rev = users.loc[mask, "revenue_d0_90"].to_numpy(dtype=float)
            s = ch["revenue_share"] * rev + ch["cost_per_session"]
        elif model == "fixed_monthly":
            s = np.full(mask.sum(), ch["monthly_cost"] * months / counts[name])
        else:
            s = np.zeros(mask.sum())
        spend.loc[mask] = s * m
    return spend


def economics_table(
    users: pd.DataFrame,
    spend: pd.Series,
    by: str,
    purchase_window: int,
    margin: float,
    rankable: set[str] | None = None,
    min_purchasers: int = 0,
) -> pd.DataFrame:
    """Per-group CAC, cost per new user, 90-day revenue per user, ROI and LTV:CAC."""
    buyers = users["first_purchase_day"].le(purchase_window).fillna(False)
    df = pd.DataFrame(
        {
            by: users[by].to_numpy(),
            "new_users": 1,
            "purchasers": buyers.to_numpy(dtype=int),
            "revenue_90d": users["revenue_d0_90"].to_numpy(dtype=float),
            "spend": spend.to_numpy(dtype=float),
        }
    )
    g = df.groupby(by)[["new_users", "purchasers", "revenue_90d", "spend"]].sum()
    g["gross_profit_90d"] = g["revenue_90d"] * margin
    has_buyers = g["purchasers"] > 0
    has_spend = g["spend"] > 0
    with np.errstate(divide="ignore", invalid="ignore"):
        g["cac"] = np.where(has_buyers, g["spend"] / g["purchasers"], np.nan)
        g["cost_per_new_user"] = g["spend"] / g["new_users"]
        g["revenue_per_user_90d"] = g["revenue_90d"] / g["new_users"]
        g["revenue_per_purchaser_90d"] = np.where(
            has_buyers, g["revenue_90d"] / g["purchasers"], np.nan
        )
        roi = (g["gross_profit_90d"] - g["spend"]) / g["spend"]
        g["roi_90d"] = np.where(has_spend, roi, np.nan)
        gp_per_buyer = np.where(has_buyers, g["gross_profit_90d"] / g["purchasers"], np.nan)
        g["ltv_to_cac"] = np.where(g["cac"] > 0, gp_per_buyer / g["cac"], np.nan)
    g.index.name = by
    g = g.reset_index()
    if rankable is not None:
        g["rankable_channel"] = g[by].isin(rankable)
        g["enough_purchasers"] = g["purchasers"] >= min_purchasers
        g["ranked"] = (
            g["rankable_channel"]
            & g["enough_purchasers"]
            & has_spend.to_numpy()
            & has_buyers.to_numpy()
        )
    return g


def pick_cut_scale(econ: pd.DataFrame, by: str = "channel") -> tuple[str, str]:
    """Among ranked rows: cut the lowest ROI, scale the highest ROI."""
    ranked = econ[econ["ranked"]].sort_values("roi_90d")
    if len(ranked) < 2:
        raise ValueError("Need at least two ranked channels to pick cut and scale")
    return ranked.iloc[0][by], ranked.iloc[-1][by]


def reallocation_impact(
    econ: pd.DataFrame,
    cut: str,
    scale: str,
    margin: float,
    marginal_cac_penalty: float,
    scale_max_multiple: float | None = None,
) -> dict:
    """Cut all of `cut`'s spend; move part of it to `scale`, bank the rest.

    `scale` absorbs at most (scale_max_multiple - 1) x its current spend (None = no cap), at a
    marginal CAC of (1 + penalty) x its average. Whatever is not moved is banked as savings.
    Gains assume each extra purchaser on `scale` brings its current average 90-day revenue.
    Losses assume cutting `cut` loses all of its purchasers and 90-day revenue (an upper bound,
    since some of those users would arrive anyway).
    Net profit change = gross profit gained - gross profit lost + spend banked.
    """
    e = econ.set_index("channel")
    x, y = e.loc[cut], e.loc[scale]
    cut_spend = float(x["spend"])
    if scale_max_multiple is None:
        moved = cut_spend
    else:
        moved = min(cut_spend, (scale_max_multiple - 1) * float(y["spend"]))
    banked = cut_spend - moved
    marginal_cac = float(y["cac"]) * (1 + marginal_cac_penalty)
    gained_purchasers = moved / marginal_cac
    gained_revenue = gained_purchasers * float(y["revenue_per_purchaser_90d"])
    lost_purchasers = float(x["purchasers"])
    lost_revenue = float(x["revenue_90d"])
    net_gp = (gained_revenue - lost_revenue) * margin
    return {
        "cut": cut,
        "scale": scale,
        "cut_spend": cut_spend,
        "scale_spend_before": float(y["spend"]),
        "spend_banked": banked,
        "net_profit_change_90d": net_gp + banked,
        "spend_moved": moved,
        "scale_avg_cac": float(y["cac"]),
        "scale_marginal_cac": marginal_cac,
        "gained_purchasers": gained_purchasers,
        "gained_revenue_90d": gained_revenue,
        "gained_gross_profit_90d": gained_revenue * margin,
        "lost_purchasers": lost_purchasers,
        "lost_revenue_90d": lost_revenue,
        "lost_gross_profit_90d": lost_revenue * margin,
        "net_purchasers": gained_purchasers - lost_purchasers,
        "net_revenue_90d": gained_revenue - lost_revenue,
        "net_gross_profit_90d": (gained_revenue - lost_revenue) * margin,
    }
