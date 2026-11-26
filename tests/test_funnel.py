import pandas as pd
from conftest import END, make_users

from campaign_perf.funnel import funnel_table, user_stage_flags

W, RW = 30, 90
OLD = END - pd.Timedelta(days=200)


def users():
    return make_users(
        [
            # 0 A: signup + purchase day 5, second purchase day 50 (gap 45 <= 90) -> repeat
            {
                "channel": "A",
                "signup_day": 0,
                "first_purchase_day": 5,
                "second_purchase_day": 50,
            },
            # 1 A: guest purchaser (no signup)
            {"channel": "A", "first_purchase_day": 2},
            # 2 A: signup only
            {"channel": "A", "signup_day": 1},
            # 3 A: purchase at day 40 > window 30 -> not a purchaser
            {"channel": "A", "signup_day": 1, "first_purchase_day": 40},
            # 4 B: purchaser, second purchase 100 days later (> 90) -> not repeat
            {
                "channel": "B",
                "signup_day": 0,
                "first_purchase_day": 0,
                "second_purchase_day": 100,
            },
            # 5 B: first purchase 60 days before end -> repeat-censored despite +10 repeat
            {
                "channel": "B",
                "first_date": END - pd.Timedelta(days=70),
                "signup_day": 0,
                "first_purchase_day": 10,
                "second_purchase_day": 20,
            },
            # 6 B: visitor only
            {"channel": "B"},
        ]
    )


def table():
    return funnel_table(users(), "channel", W, RW, END).set_index("channel")


def test_stage_counts():
    t = table()
    # A: 4 users, signups 3 (0,2,3), purchasers 2 (0,1), after signup 1 (0),
    #    repeat eligible 2 (0,1), repeat 1 (0)
    a = t.loc["A"]
    assert (a.new_users, a.signups, a.purchasers, a.purchasers_after_signup) == (4, 3, 2, 1)
    assert (a.purchasers_repeat_eligible, a.repeat_purchasers) == (2, 1)
    # B: 3 users, signups 2, purchasers 2, after signup 2, eligible 1 (5 censored), repeat 0
    b = t.loc["B"]
    assert (b.new_users, b.signups, b.purchasers, b.purchasers_after_signup) == (3, 2, 2, 2)
    assert (b.purchasers_repeat_eligible, b.repeat_purchasers) == (1, 0)


def test_nesting():
    t = table()
    assert (t.purchasers_after_signup <= t.signups).all()
    assert (t.purchasers_after_signup <= t.purchasers).all()
    assert (t.repeat_purchasers <= t.purchasers_repeat_eligible).all()
    assert (t.purchasers_repeat_eligible <= t.purchasers).all()


def test_guest_purchaser():
    f = user_stage_flags(users(), W, RW, END)
    assert f.loc[1, "purchase"] and not f.loc[1, "purchase_after_signup"]


def test_purchase_after_window_excluded():
    f = user_stage_flags(users(), W, RW, END)
    assert not f.loc[3, "purchase"]


def test_repeat_rules():
    f = user_stage_flags(users(), W, RW, END)
    assert f.loc[0, "repeat"]
    assert f.loc[4, "repeat_eligible"] and not f.loc[4, "repeat"]  # gap 100 > 90
    assert not f.loc[5, "repeat_eligible"] and not f.loc[5, "repeat"]  # censored


def test_repeat_eligibility_boundary():
    # first purchase exactly end - 90 days -> eligible; one day later -> not
    u = make_users(
        [
            {
                "first_date": END - pd.Timedelta(days=90),
                "first_purchase_day": 0,
                "second_purchase_day": 1,
            },
            {
                "first_date": END - pd.Timedelta(days=89),
                "first_purchase_day": 0,
                "second_purchase_day": 1,
            },
        ]
    )
    f = user_stage_flags(u, W, RW, END)
    assert list(f.repeat_eligible) == [True, False]
    assert list(f.repeat) == [True, False]


def test_total_row_is_sum():
    t = table()
    counts = [
        "new_users",
        "signups",
        "purchasers",
        "purchasers_after_signup",
        "purchasers_repeat_eligible",
        "repeat_purchasers",
    ]
    assert (t.loc["All channels", counts] == t.loc[["A", "B"], counts].sum()).all()
    assert t.loc["All channels", "purchase_rate"] == 4 / 7
