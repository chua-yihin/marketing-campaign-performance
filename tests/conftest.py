import numpy as np
import pandas as pd
import pytest

NAN = np.nan
END = pd.Timestamp("2017-08-01")

FLOAT_COLS = [
    "signup_day",
    "first_purchase_day",
    "second_purchase_day",
    "first_return_day",
    "first_purchase_return_day",
    "revenue_d0_90",
]


def make_users(rows):
    """Build a user frame; milestone columns default to NaN (never), revenue to 0."""
    defaults = {
        "channel": "A",
        "campaign": "(not set)",
        "first_date": END - pd.Timedelta(days=200),
        **{c: NAN for c in FLOAT_COLS},
        "revenue_d0_90": 0.0,
    }
    out = [{"fullVisitorId": f"u{i}", **defaults, **r} for i, r in enumerate(rows)]
    df = pd.DataFrame(out)
    df["first_date"] = pd.to_datetime(df["first_date"])
    df[FLOAT_COLS] = df[FLOAT_COLS].astype(float)
    return df


@pytest.fixture
def end_date():
    return END
