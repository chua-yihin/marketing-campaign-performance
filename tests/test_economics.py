import numpy as np
import pandas as pd
import pytest
from conftest import make_users

from campaign_perf.economics import (
    economics_table,
    months_between,
    pick_cut_scale,
    reallocation_impact,
    user_spend,
)

CFG = {
    "Paid": {"model": "per_session", "cost_per_session": 2.0},
    "Aff": {"model": "revenue_share", "revenue_share": 0.1, "cost_per_session": 1.0},
    "Disp": {"model": "fixed_monthly", "monthly_cost": 300.0},
    "Org": {"model": "none"},
}


def spend_users():
    return make_users(
        [
            {"channel": "Paid"},
            {"channel": "Paid"},
            {"channel": "Aff", "revenue_d0_90": 100.0},
            {"channel": "Aff", "revenue_d0_90": 0.0},
            {"channel": "Disp"},
            {"channel": "Disp"},
            {"channel": "Disp"},
            {"channel": "Org"},
        ]
    )


def test_user_spend_models():
    u = spend_users()
    s = user_spend(u, CFG, months=2.0)
    # Paid 2 each; Aff 0.1*100+1 = 11 and 1; Disp 300*2/3 = 200 each; Org 0
    assert list(s) == pytest.approx([2, 2, 11, 1, 200, 200, 200, 0])
    assert s[u.channel == "Disp"].sum() == pytest.approx(600.0)  # monthly_cost x months


def test_multiplier_scalar_and_dict():
    u = spend_users()
    base = user_spend(u, CFG, 2.0)
    assert list(user_spend(u, CFG, 2.0, 1.5)) == pytest.approx(list(base * 1.5))
    s = user_spend(u, CFG, 2.0, {"Paid": 0.5, "Disp": 2.0})
    assert list(s) == pytest.approx([1, 1, 11, 1, 400, 400, 400, 0])


def test_months_between():
    s, e = pd.Timestamp("2016-08-01"), pd.Timestamp("2017-07-31")
    assert months_between(s, e) == pytest.approx(365 / (365.25 / 12))
    assert months_between(s, s) == pytest.approx(12 / 365.25)


def econ_users():
    rows = []
    # A: 4 users, 2 purchasers, revenue 200, spend 4 x 25 = 100
    rows += [{"channel": "A", "first_purchase_day": 0, "revenue_d0_90": 100.0}] * 2
    rows += [{"channel": "A"}] * 2
    # B: 2 users, 1 purchaser (day 10), revenue 50, spend 2 x 50 = 100
    rows += [{"channel": "B", "first_purchase_day": 10, "revenue_d0_90": 50.0}, {"channel": "B"}]
    # C: zero purchasers, spend 30
    rows += [{"channel": "C"}]
    # D: purchase at day 40 (outside 30-day window), no spend
    rows += [{"channel": "D", "first_purchase_day": 40, "revenue_d0_90": 10.0}]
    u = make_users(rows)
    spend = pd.Series([25.0] * 4 + [50.0] * 2 + [30.0] + [0.0], index=u.index)
    return u, spend


def econ(**kw):
    u, s = econ_users()
    return economics_table(u, s, "channel", 30, 0.5, **kw).set_index("channel")


def test_economics_metrics():
    e = econ()
    a = e.loc["A"]
    assert a.cac == 50  # 100 / 2
    assert a.cost_per_new_user == 25
    assert a.revenue_per_user_90d == 50
    assert a.roi_90d == pytest.approx((200 * 0.5 - 100) / 100)  # 0
    # LTV:CAC = (100 gross profit / 2 purchasers) / 50 = 1
    assert a.ltv_to_cac == pytest.approx(1.0)
    b = e.loc["B"]
    assert b.cac == 100
    assert b.roi_90d == pytest.approx((25 - 100) / 100)
    assert b.ltv_to_cac == pytest.approx(25 / 100)


def test_zero_purchaser_channel_nan():
    e = econ(rankable={"A", "B", "C", "D"}, min_purchasers=1)
    c = e.loc["C"]
    assert c.purchasers == 0
    assert np.isnan(c.cac) and np.isnan(c.ltv_to_cac)
    assert c.roi_90d == -1.0
    assert not c.ranked
    # D: purchase outside window -> 0 purchasers; no spend -> NaN ROI, not ranked
    assert e.loc["D", "purchasers"] == 0 and np.isnan(e.loc["D", "roi_90d"])
    assert not e.loc["D", "ranked"]


def test_zero_purchaser_never_ranked_even_with_min_zero():
    e = econ(rankable={"A", "B", "C"}, min_purchasers=0)
    assert not e.loc["C", "ranked"]


def test_ranked_rules():
    e = econ(rankable={"A", "B"}, min_purchasers=2)
    assert e.loc["A", "ranked"]
    assert not e.loc["B", "ranked"]  # 1 purchaser < 2
    assert not e.loc["C", "ranked"]  # not rankable
    assert econ(rankable={"A", "B"}, min_purchasers=1).loc["B", "ranked"]


def test_pick_cut_scale():
    e = econ(rankable={"A", "B"}, min_purchasers=1).reset_index()
    assert pick_cut_scale(e) == ("B", "A")  # ROI B -0.75, A 0
    with pytest.raises(ValueError):
        pick_cut_scale(econ(rankable={"A"}, min_purchasers=1).reset_index())


def test_reallocation_impact():
    econ_df = pd.DataFrame(
        {
            "channel": ["X", "Y"],
            "spend": [130.0, 200.0],
            "purchasers": [2.0, 4.0],
            "revenue_90d": [60.0, 400.0],
            "cac": [65.0, 50.0],
            "revenue_per_purchaser_90d": [30.0, 100.0],
        }
    )
    r = reallocation_impact(econ_df, "X", "Y", margin=0.5, marginal_cac_penalty=0.3)
    # marginal CAC = 50 x 1.3 = 65; gained = 130 / 65 = 2 buyers -> 200 revenue
    assert r["scale_marginal_cac"] == pytest.approx(65.0)
    assert r["gained_purchasers"] == pytest.approx(2.0)
    assert r["gained_revenue_90d"] == pytest.approx(200.0)
    assert r["gained_gross_profit_90d"] == pytest.approx(100.0)
    assert r["lost_purchasers"] == 2.0 and r["lost_revenue_90d"] == 60.0
    assert r["net_purchasers"] == pytest.approx(0.0)
    assert r["net_revenue_90d"] == pytest.approx(140.0)
    assert r["net_gross_profit_90d"] == pytest.approx(70.0)


def test_reallocation_cap_banks_the_rest():
    econ_df = pd.DataFrame(
        {
            "channel": ["X", "Y"],
            "spend": [1000.0, 100.0],
            "purchasers": [2.0, 4.0],
            "revenue_90d": [60.0, 400.0],
            "cac": [500.0, 25.0],
            "revenue_per_purchaser_90d": [30.0, 100.0],
        }
    )
    r = reallocation_impact(
        econ_df, "X", "Y", margin=0.5, marginal_cac_penalty=0.3, scale_max_multiple=2.0
    )
    # Y can grow to 2x: moved = 100, banked = 900; marginal CAC 32.5 -> 100/32.5 buyers
    assert r["spend_moved"] == pytest.approx(100.0)
    assert r["spend_banked"] == pytest.approx(900.0)
    gained_rev = 100.0 / 32.5 * 100.0
    assert r["gained_revenue_90d"] == pytest.approx(gained_rev)
    # net profit = (gained rev - lost rev) x margin + banked
    assert r["net_profit_change_90d"] == pytest.approx((gained_rev - 60.0) * 0.5 + 900.0)
