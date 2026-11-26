"""Plotly figures with one consistent palette. Every title states the chart's finding.

Colour does one job: it picks out the two channels the memo is about. The channel to scale is
blue, the channel to cut is orange, every other channel is neutral grey, and the all-channel
average is a dashed dark line. Channel names sit on the axis or as direct labels, so identity
never relies on colour alone.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Palette (reference data-viz palette; blue/orange are categorical slots 1-2, validated pair)
SCALE = "#2a78d6"
CUT = "#eb6834"
OTHER = "#b8b7b1"
AVERAGE = "#52514e"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e7e6e2"
SURFACE = "#fcfcfb"
FONT = "Inter, Segoe UI, Helvetica, Arial, sans-serif"

EXCLUDE_FROM_CHARTS = {"(Other)"}  # 25 users: too small to show


def channel_color(channel: str, cut: str, scale: str) -> str:
    if channel == scale:
        return SCALE
    if channel == cut:
        return CUT
    return OTHER


def _layout(fig: go.Figure, title: str, subtitle: str, height: int = 460) -> go.Figure:
    # A pair of "$" in a Plotly string switches it to LaTeX; use the HTML entity instead.
    title, subtitle = title.replace("$", "&#36;"), subtitle.replace("$", "&#36;")
    fig.update_layout(
        title={
            "text": f"<b>{title}</b><br><span style='font-size:13px;color:{TEXT_2}'>"
            f"{subtitle}</span>",
            "x": 0,
            "xanchor": "left",
            "font": {"size": 17, "color": TEXT},
        },
        font={"family": FONT, "size": 13, "color": TEXT_2},
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        margin={"l": 10, "r": 30, "t": 90, "b": 50},
        height=height,
        showlegend=False,
        hoverlabel={"bgcolor": "white", "font": {"family": FONT, "color": TEXT}},
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, ticks="")
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, ticks="")
    return fig


def _pct(x: float, digits: int = 1) -> str:
    return f"{100 * x:.{digits}f}%"


def funnel_chart(funnel: pd.DataFrame, cut: str, scale: str) -> go.Figure:
    """Four funnel step rates per channel, each with its Wilson 95% CI."""
    df = funnel[~funnel["channel"].isin(EXCLUDE_FROM_CHARTS | {"All channels"})]
    avg = funnel.set_index("channel").loc["All channels"]
    df = df.sort_values("purchase_rate")
    steps = [
        ("signup_rate", "Visit → sign-up"),
        ("purchase_rate", "Visit → purchase (any)"),
        ("signup_to_purchase", "Sign-up → purchase"),
        ("repeat_rate", "Purchase → repeat (90 d)"),
    ]
    fig = make_subplots(
        rows=1,
        cols=4,
        shared_yaxes=True,
        subplot_titles=[s[1] for s in steps],
        horizontal_spacing=0.03,
    )
    colors = [channel_color(c, cut, scale) for c in df["channel"]]
    for i, (col, label) in enumerate(steps, start=1):
        rate = df[col].to_numpy()
        fig.add_trace(
            go.Bar(
                x=rate,
                y=df["channel"],
                orientation="h",
                marker={"color": colors, "cornerradius": 4},
                error_x={
                    "type": "data",
                    "symmetric": False,
                    "array": df[f"{col}_hi"] - rate,
                    "arrayminus": rate - df[f"{col}_lo"],
                    "color": TEXT_2,
                    "thickness": 1.2,
                    "width": 3,
                },
                customdata=np.stack([df[f"{col}_lo"], df[f"{col}_hi"]], axis=1),
                hovertemplate=f"<b>%{{y}}</b><br>{label}: %{{x:.2%}}"
                "<br>95% CI %{customdata[0]:.2%}–%{customdata[1]:.2%}<extra></extra>",
            ),
            row=1,
            col=i,
        )
        fig.add_vline(
            x=avg[col], line={"color": AVERAGE, "dash": "dash", "width": 1.5}, row=1, col=i
        )
        fig.update_xaxes(tickformat=".0%", row=1, col=i, rangemode="tozero")
    fig.update_annotations(font={"size": 13, "color": TEXT})

    s, c = df.set_index("channel").loc[scale], df.set_index("channel").loc[cut]
    title = (
        f"{scale} turns {_pct(s['purchase_rate'])} of new visitors into buyers; "
        f"{cut} only {_pct(c['purchase_rate'], 2)}"
    )
    subtitle = (
        f"Funnel step rates within 90 days of first visit, by acquiring channel. "
        f"Dashed line = all-channel average ({_pct(avg['purchase_rate'], 2)} visit → purchase). "
        "Whiskers = Wilson 95% CI."
    )
    return _layout(fig, title, subtitle, height=440)


def cac_vs_value_chart(econ: pd.DataFrame, cut: str, scale: str) -> go.Figure:
    """CAC (log x) vs 90-day revenue per acquired user; bubble area = new users."""
    df = econ[econ["spend"] > 0].copy()
    df = df[df["purchasers"] > 0]
    size = np.sqrt(df["new_users"] / df["new_users"].max()) * 70 + 10
    colors = [channel_color(c, cut, scale) for c in df["channel"]]
    fig = go.Figure(
        go.Scatter(
            x=df["cac"],
            y=df["revenue_per_user_90d"],
            mode="markers+text",
            text=df["channel"],
            textposition="top center",
            textfont={"color": TEXT, "size": 13},
            marker={
                "size": size,
                "color": colors,
                "opacity": 0.85,
                "line": {"color": SURFACE, "width": 2},
            },
            customdata=np.stack(
                [df["new_users"], df["purchasers"], df["spend"], df["roi_90d"]], axis=1
            ),
            hovertemplate="<b>%{text}</b><br>CAC: $%{x:,.0f}<br>90-day revenue per new user: "
            "$%{y:.2f}<br>New users: %{customdata[0]:,.0f}<br>Purchasers: %{customdata[1]:,.0f}"
            "<br>Assumed spend: $%{customdata[2]:,.0f}<br>ROI: %{customdata[3]:.0%}"
            "<extra></extra>",
        )
    )
    ticks = [3, 10, 30, 100, 300, 1000, 3000]
    fig.update_xaxes(
        type="log",
        title="CAC: assumed spend per first-time purchaser (log scale)",
        tickvals=ticks,
        ticktext=[f"&#36;{v:,}" for v in ticks],
    )
    ymax = float(df["revenue_per_user_90d"].max())
    fig.update_yaxes(
        title="90-day revenue per new user", tickprefix="&#36;", range=[-0.12 * ymax, 1.15 * ymax]
    )
    e = df.set_index("channel")
    title = (
        f"{scale} buys a customer for ${e.loc[scale, 'cac']:,.0f}; "
        f"{cut} pays ${e.loc[cut, 'cac']:,.0f} for one"
    )
    subtitle = (
        "Better channels sit top-left: cheap customers, high revenue per visitor. "
        "Bubble area = new users acquired. Channels with no assumed spend are not shown."
    )
    return _layout(fig, title, subtitle, height=480)


def roi_chart(econ: pd.DataFrame, sensitivity: pd.DataFrame, cut: str, scale: str) -> go.Figure:
    """90-day ROI by channel at base spend, whiskers = spend x0.5 .. x1.5."""
    df = econ[econ["spend"] > 0].sort_values("roi_90d").copy()
    wide = sensitivity.pivot(index="channel", columns="multiplier", values="roi_90d")
    lo_m, hi_m = min(wide.columns), max(wide.columns)
    df["roi_best"] = df["channel"].map(wide[lo_m])  # cheaper spend -> higher ROI
    df["roi_worst"] = df["channel"].map(wide[hi_m])
    labels = [
        f"{c}{'' if r else ' (too few buyers to rank)'}"
        for c, r in zip(df["channel"], df["ranked"], strict=True)
    ]
    fig = go.Figure(
        go.Bar(
            x=df["roi_90d"],
            y=labels,
            orientation="h",
            marker={
                "color": [channel_color(c, cut, scale) for c in df["channel"]],
                "cornerradius": 4,
            },
            error_x={
                "type": "data",
                "symmetric": False,
                "array": df["roi_best"] - df["roi_90d"],
                "arrayminus": df["roi_90d"] - df["roi_worst"],
                "color": TEXT_2,
                "thickness": 1.2,
                "width": 4,
            },
            customdata=np.stack([df["roi_worst"], df["roi_best"], df["spend"]], axis=1),
            hovertemplate="<b>%{y}</b><br>ROI (base spend): %{x:.0%}<br>Spend +50%: "
            "%{customdata[0]:.0%} · Spend −50%: %{customdata[1]:.0%}"
            "<br>Assumed spend: $%{customdata[2]:,.0f}<extra></extra>",
        )
    )
    fig.add_vline(x=0, line={"color": TEXT_2, "width": 1})
    for label, roi, lo, hi in zip(
        labels, df["roi_90d"], df["roi_worst"], df["roi_best"], strict=True
    ):
        fig.add_annotation(
            x=1.0,
            xref="paper",
            y=label,
            xanchor="left",
            xshift=8,
            showarrow=False,
            text=f"<b>{roi:+.0%}</b>  <span style='color:{TEXT_2}'>({lo:+.0%} to {hi:+.0%})</span>",
            font={"color": TEXT, "size": 13},
        )
    fig.update_xaxes(tickformat=".0%", title="90-day ROI = (revenue × 40% margin − spend) ÷ spend")
    e = df.set_index("channel")
    winners = df[(df["roi_worst"] > 0) & df["ranked"]]["channel"].tolist()
    title = (
        f"Only {' and '.join(winners)} pay back their assumed spend in 90 days; "
        f"{cut} returns {1 + e.loc[cut, 'roi_90d']:.0%} of each dollar"
        if winners
        else f"{cut} returns {1 + e.loc[cut, 'roi_90d']:.0%} of each dollar"
    )
    subtitle = (
        "Whiskers: ROI if the channel's assumed spend were 50% lower (right) or 50% higher (left). "
        "Direct and (Other) have no spend model and are not shown."
    )
    fig = _layout(fig, title, subtitle, height=420)
    fig.update_layout(margin={"r": 190})
    return fig


def retention_chart(retention: pd.DataFrame, cut: str, scale: str) -> go.Figure:
    """30/60/90-day retention lines by channel, highlighted channels labelled at the line end."""
    df = retention[~retention["channel"].isin(EXCLUDE_FROM_CHARTS)]
    fig = go.Figure()
    order = sorted(df["channel"].unique(), key=lambda c: (c in (cut, scale, "All channels"), c))
    labels: list[tuple[float, str, bool]] = []
    for ch in order:
        d = df[df["channel"] == ch].sort_values("window_days")
        is_avg = ch == "All channels"
        color = AVERAGE if is_avg else channel_color(ch, cut, scale)
        emph = is_avg or ch in (cut, scale)
        fig.add_trace(
            go.Scatter(
                x=d["window_days"],
                y=d["retention"],
                mode="lines+markers",
                name=ch,
                line={
                    "color": color,
                    "width": 2.5 if emph else 1.5,
                    "dash": "dash" if is_avg else "solid",
                },
                marker={"size": 8, "color": color, "line": {"color": SURFACE, "width": 2}},
                error_y={
                    "type": "data",
                    "symmetric": False,
                    "array": d["retention_hi"] - d["retention"],
                    "arrayminus": d["retention"] - d["retention_lo"],
                    "color": color,
                    "thickness": 1,
                    "width": 3,
                    "visible": emph,
                },
                customdata=np.stack(
                    [d["eligible_users"], d["retention_lo"], d["retention_hi"]], axis=1
                ),
                hovertemplate=f"<b>{ch}</b><br>Day %{{x}}: %{{y:.1%}} returned"
                "<br>95% CI %{customdata[1]:.1%}–%{customdata[2]:.1%}"
                "<br>Eligible users: %{customdata[0]:,.0f}<extra></extra>",
            )
        )
        labels.append((float(d.iloc[-1]["retention"]), ch, emph))
    last_x = int(df["window_days"].max())
    gap = 0.045 * max(y for y, _, _ in labels)
    placed: list[float] = []
    for y, ch, emph in sorted(labels):
        y_label = max(y, placed[-1] + gap) if placed else y
        placed.append(y_label)
        fig.add_annotation(
            x=last_x,
            y=y_label,
            text=ch,
            xanchor="left",
            xshift=10,
            showarrow=False,
            font={"color": TEXT if emph else TEXT_2, "size": 13 if emph else 11},
        )
    fig.update_xaxes(
        tickvals=[30, 60, 90], ticktext=["Day 30", "Day 60", "Day 90"], range=[25, 112]
    )
    fig.update_yaxes(
        tickformat=".0%", rangemode="tozero", title="Share of new users with any visit on days 1..N"
    )
    r = df[df["window_days"] == 90].set_index("channel")["retention"]
    title = (
        f"{scale} visitors come back most ({_pct(r[scale])} by day 90); "
        f"{cut} visitors least ({_pct(r[cut])})"
    )
    subtitle = (
        f"All-channel average {_pct(r['All channels'])} (dashed). Each point counts only users "
        "with at least N days of data. Whiskers = Wilson 95% CI on highlighted lines."
    )
    return _layout(fig, title, subtitle, height=480)
