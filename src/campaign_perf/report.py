"""Render docs/index.html and reports/figures/*.png from reports/tables/*.csv.

Every number shown is read from the CSV tables written by `make analyze`; nothing is typed by hand.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from campaign_perf import charts
from campaign_perf.config import DOCS_DIR, FIGURES_DIR, TABLES_DIR, load_config

TEMPLATES = Path(__file__).parent / "templates"


def load_tables(tables_dir: Path = TABLES_DIR) -> dict[str, pd.DataFrame]:
    names = [
        "funnel_by_channel",
        "economics_by_channel",
        "retention_by_channel",
        "sensitivity",
        "sensitivity_summary",
        "reallocation_impact",
    ]
    return {n: pd.read_csv(tables_dir / f"{n}.csv") for n in names}


def money(x: float, digits: int = 0) -> str:
    sign = "−" if x < 0 else ""
    return f"{sign}${abs(x):,.{digits}f}"


def money_k(x: float) -> str:
    sign = "+" if x >= 0 else "−"
    return f"{sign}${abs(x) / 1000:,.0f}k"


def facts(t: dict[str, pd.DataFrame]) -> dict:
    """Every headline number used by the dashboard and the memo, computed from the tables."""
    imp = t["reallocation_impact"].set_index("scenario")
    base, low, high = imp.loc["base"], imp.loc["low"], imp.loc["high"]
    cut, scale = base["cut"], base["scale"]
    econ = t["economics_by_channel"].set_index("channel")
    ret90 = t["retention_by_channel"].query("window_days == 90").set_index("channel")
    funnel = t["funnel_by_channel"].set_index("channel")
    sens = t["sensitivity_summary"]
    ranked = econ[econ["ranked"]]
    return {
        "cut": cut,
        "scale": scale,
        "cut_spend": base["cut_spend"],
        "cut_cac": econ.loc[cut, "cac"],
        "scale_cac": econ.loc[scale, "cac"],
        "cut_roi": econ.loc[cut, "roi_90d"],
        "scale_roi": econ.loc[scale, "roi_90d"],
        "cut_purchasers": int(econ.loc[cut, "purchasers"]),
        "scale_purchasers": int(econ.loc[scale, "purchasers"]),
        "cut_new_users": int(econ.loc[cut, "new_users"]),
        "scale_new_users": int(econ.loc[scale, "new_users"]),
        "spend_total": econ["spend"].sum(),
        "cut_spend_share": base["cut_spend"] / econ["spend"].sum(),
        "ranked_avg_cac": ranked["spend"].sum() / ranked["purchasers"].sum(),
        "ranked_avg_roi": (ranked["gross_profit_90d"].sum() - ranked["spend"].sum())
        / ranked["spend"].sum(),
        "cut_ret90": ret90.loc[cut, "retention"],
        "scale_ret90": ret90.loc[scale, "retention"],
        "avg_ret90": ret90.loc["All channels", "retention"],
        "cut_purchase_rate": funnel.loc[cut, "purchase_rate"],
        "scale_purchase_rate": funnel.loc[scale, "purchase_rate"],
        "avg_purchase_rate": funnel.loc["All channels", "purchase_rate"],
        "spend_moved": base["spend_moved"],
        "spend_banked": base["spend_banked"],
        "gained_purchasers": base["gained_purchasers"],
        "lost_purchasers": base["lost_purchasers"],
        "net_purchasers": base["net_purchasers"],
        "gained_revenue": base["gained_revenue_90d"],
        "lost_revenue": base["lost_revenue_90d"],
        "net_revenue": base["net_revenue_90d"],
        "net_gross_profit": base["net_gross_profit_90d"],
        "net_profit": base["net_profit_change_90d"],
        "net_profit_low": low["net_profit_change_90d"],
        "net_profit_high": high["net_profit_change_90d"],
        "net_gross_profit_low": low["net_gross_profit_90d"],
        "net_gross_profit_high": high["net_gross_profit_90d"],
        "scenarios_total": len(sens),
        "scenarios_hold": int(sens["recommendation_holds"].sum()),
        "scenarios_cut_hold": int(sens["same_cut"].sum()),
        "flips": sens.loc[~sens["recommendation_holds"], "scenario"].tolist(),
        "flip_alternative": sens.loc[~sens["same_scale"], "scale"].unique().tolist(),
    }


def table_html(df: pd.DataFrame) -> Markup:
    return Markup(df.to_html(index=False, border=0, escape=True))


def economics_view(econ: pd.DataFrame) -> pd.DataFrame:
    e = econ[~econ["channel"].isin(charts.EXCLUDE_FROM_CHARTS)].sort_values(
        "roi_90d", ascending=False, na_position="last"
    )
    return pd.DataFrame(
        {
            "Channel": e["channel"],
            "New users": e["new_users"].map("{:,}".format),
            "Purchasers": e["purchasers"].map("{:,}".format),
            "Assumed spend": e["spend"].map(money),
            "CAC": e["cac"].map(lambda v: money(v) if pd.notna(v) and v > 0 else "–"),
            "90-day revenue / user": e["revenue_per_user_90d"].map(lambda v: money(v, 2)),
            "ROI (90 d)": e["roi_90d"].map(lambda v: f"{v:+.0%}" if pd.notna(v) else "–"),
            "LTV:CAC": e["ltv_to_cac"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "–"),
            "Ranked": e["ranked"].map({True: "yes", False: "no"}),
        }
    )


def funnel_view(funnel: pd.DataFrame) -> pd.DataFrame:
    f = funnel[~funnel["channel"].isin(charts.EXCLUDE_FROM_CHARTS)]

    def rate(col):
        return [
            f"{r:.2%} ({lo:.2%}–{hi:.2%})" if pd.notna(r) else "–"
            for r, lo, hi in zip(f[col], f[f"{col}_lo"], f[f"{col}_hi"], strict=True)
        ]

    return pd.DataFrame(
        {
            "Channel": f["channel"],
            "New users": f["new_users"].map("{:,}".format),
            "Sign-ups": f["signups"].map("{:,}".format),
            "Visit → sign-up": rate("signup_rate"),
            "Purchasers": f["purchasers"].map("{:,}".format),
            "Visit → purchase": rate("purchase_rate"),
            "Sign-up → purchase": rate("signup_to_purchase"),
            "Repeat rate": rate("repeat_rate"),
        }
    )


def retention_view(ret: pd.DataFrame) -> pd.DataFrame:
    r = ret[~ret["channel"].isin(charts.EXCLUDE_FROM_CHARTS)]
    wide = r.pivot(index="channel", columns="window_days", values="retention")
    elig = r.pivot(index="channel", columns="window_days", values="eligible_users")
    out = pd.DataFrame({"Channel": wide.index})
    for n in wide.columns:
        out[f"Day {n}"] = [f"{v:.1%}" for v in wide[n]]
    out["Eligible users (day 90)"] = [f"{v:,}" for v in elig[max(elig.columns)]]
    return out


def assumptions_view(cfg: dict) -> pd.DataFrame:
    rows = []
    for name, ch in cfg["channels"].items():
        model = ch["model"]
        if model == "per_session":
            desc = f"${ch['cost_per_session']:.2f} per new-user session"
        elif model == "revenue_share":
            desc = (
                f"{ch['revenue_share']:.0%} of 90-day revenue + "
                f"${ch['cost_per_session']:.2f} per session"
            )
        elif model == "fixed_monthly":
            desc = f"${ch['monthly_cost']:,.0f} per month, fixed"
        else:
            desc = "$0 (no spend model)"
        rows.append(
            {"Channel": name, "Assumed cost": desc, "Ranked": "yes" if ch["rank"] else "no"}
        )
    e = cfg["economics"]
    rows.append(
        {"Channel": "Gross margin", "Assumed cost": f"{e['gross_margin']:.0%}", "Ranked": ""}
    )
    rows.append(
        {
            "Channel": "Scale-up limit",
            "Assumed cost": f"scaled channel grows to at most {e['scale_max_multiple']:g}x its "
            f"spend, marginal CAC {e['scale_marginal_cac_penalty']:.0%} worse",
            "Ranked": "",
        }
    )
    return pd.DataFrame(rows)


def build_dashboard(t: dict[str, pd.DataFrame], cfg: dict, f: dict) -> tuple[str, dict]:
    cut, scale = f["cut"], f["scale"]
    figs = {
        "funnel": charts.funnel_chart(t["funnel_by_channel"], cut, scale),
        "cac_vs_value": charts.cac_vs_value_chart(t["economics_by_channel"], cut, scale),
        "roi": charts.roi_chart(t["economics_by_channel"], t["sensitivity"], cut, scale),
        "retention": charts.retention_chart(t["retention_by_channel"], cut, scale),
    }
    config = {"displaylogo": False, "responsive": True}
    html = {}
    for i, (key, fig) in enumerate(figs.items()):
        html[key] = Markup(fig.to_html(full_html=False, include_plotlyjs=(i == 0), config=config))

    headline = (
        f"Cut {cut}, scale {scale}: about {money_k(f['net_profit'])} in 90-day profit "
        f"({money_k(f['net_profit_low'])} to {money_k(f['net_profit_high'])})"
    )
    lede = (
        f"{cut} carries {f['cut_spend_share']:.0%} of assumed acquisition spend "
        f"({money(f['cut_spend'])}) but brought only {f['cut_purchasers']} first-time buyers. "
        f"{scale} acquires buyers at {money(f['scale_cac'])} each and keeps "
        f"{f['scale_ret90']:.0%} of its visitors coming back by day 90. "
        f"Most of the gain is spend no longer wasted; doubling {scale} adds about "
        f"{f['net_purchasers']:,.0f} net buyers."
    )
    tiles = [
        {
            "label": f"{cut} CAC",
            "value": money(f["cut_cac"]),
            "note": f"vs {money(f['ranked_avg_cac'])} across ranked channels",
        },
        {
            "label": f"{scale} CAC",
            "value": money(f["scale_cac"]),
            "note": f"ROI {f['scale_roi']:+.0%} in 90 days",
        },
        {
            "label": "90-day retention",
            "value": f"{f['scale_ret90']:.0%} vs {f['cut_ret90']:.0%}",
            "note": f"{scale} vs {cut}; average {f['avg_ret90']:.1%}",
        },
        {
            "label": "Recommendation holds",
            "value": f"{f['scenarios_hold']} of {f['scenarios_total']}",
            "note": "spend sensitivity scenarios (±50%)",
        },
    ]
    chart_blocks = [
        {
            "heading": "Funnel by acquiring channel",
            "html": html["funnel"],
            "table": table_html(funnel_view(t["funnel_by_channel"])),
        },
        {
            "heading": "What a customer costs vs what a visitor is worth",
            "html": html["cac_vs_value"],
            "table": table_html(economics_view(t["economics_by_channel"])),
        },
        {"heading": "Return on assumed spend", "html": html["roi"], "table": None},
        {
            "heading": "Retention of the users each channel acquired",
            "html": html["retention"],
            "table": table_html(retention_view(t["retention_by_channel"])),
        },
    ]
    caveats = [
        "Spend is assumed, not measured: the sample has no cost data. Results are shown at ±50%.",
        "First-touch attribution: each user belongs to the channel of their first session.",
        "Data is from 2016-17 (Google Merchandise Store) and may not reflect current behaviour.",
        "Sign-up is proxied by /registersuccess.html, which also fires on some logins; "
        "guest checkout means many buyers never sign up.",
        'Google staff traffic (Referral with source "(direct)") is excluded.',
        "Losing every Social purchaser when its spend is cut is an upper bound on the loss.",
    ]
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape())
    page = env.get_template("dashboard.html.j2").render(
        period=f"{cfg['data']['start_date']} to {cfg['data']['end_date']}",
        headline=headline,
        lede=lede,
        cut=cut,
        scale=scale,
        tiles=tiles,
        charts=chart_blocks,
        assumptions_table=table_html(assumptions_view(cfg)),
        caveats=caveats,
    )
    return page, figs


def export_pngs(figs: dict, out_dir: Path = FIGURES_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, fig in figs.items():
        fig.write_image(out_dir / f"{name}.png", width=1100, height=fig.layout.height, scale=2)


def main() -> None:
    cfg = load_config()
    t = load_tables()
    f = facts(t)
    page, figs = build_dashboard(t, cfg, f)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "index.html").write_text(page, encoding="utf-8")
    print(f"Wrote {DOCS_DIR / 'index.html'}")
    try:
        export_pngs(figs)
        print(f"Wrote PNGs to {FIGURES_DIR}")
    except Exception as exc:  # PNG export needs a local Chrome for kaleido
        print(f"PNG export skipped: {exc}")


if __name__ == "__main__":
    main()
