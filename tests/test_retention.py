import pandas as pd
from conftest import END, make_users

from campaign_perf.retention import retention_table


def table(u):
    t = retention_table(u, "channel", [30, 60, 90], END)
    return t[t.channel == "A"].set_index("window_days")


def test_censoring():
    u = make_users(
        [
            {"first_date": END - pd.Timedelta(days=20), "first_return_day": 1},
            {"first_date": END - pd.Timedelta(days=45), "first_return_day": 1},
        ]
    )
    t = table(u)
    # 20-day user: eligible nowhere; 45-day user: eligible only at 30
    assert list(t.eligible_users) == [1, 0, 0]
    assert list(t.retained) == [1, 0, 0]


def test_retained_threshold_and_purchase_retention():
    u = make_users(
        [
            {"first_return_day": 30, "first_purchase_return_day": 31},
            {"first_return_day": 31},
            {"first_return_day": 61, "first_purchase_return_day": 61},
            {},  # day-0 only, never returned
        ]
    )
    t = table(u)
    assert list(t.eligible_users) == [4, 4, 4]
    # retained: N=30 -> user0; N=60 -> users 0,1; N=90 -> users 0,1,2
    assert list(t.retained) == [1, 2, 3]
    # purchase retention via first_purchase_return_day: 30 -> 0; 60 -> 0; 90 -> 0,2
    assert list(t.purchase_retained) == [0, 1, 2]
    assert t.loc[90, "retention"] == 0.75


def test_total_row():
    u = make_users(
        [
            {"channel": "A", "first_return_day": 5},
            {"channel": "B", "first_return_day": 5},
            {"channel": "B"},
        ]
    )
    t = retention_table(u, "channel", [30], END).set_index("channel")
    assert t.loc["All channels", "eligible_users"] == 3
    assert t.loc["All channels", "retained"] == 2
