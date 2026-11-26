import numpy as np
import pandas as pd

from campaign_perf.stats import add_rate, wilson_ci


def test_wilson_known_value():
    lo, hi = wilson_ci(10, 100)
    assert abs(float(lo) - 0.0552) < 1e-3
    assert abs(float(hi) - 0.1744) < 1e-3


def test_wilson_zero_successes_low_is_zero():
    lo, hi = wilson_ci(0, 20)
    assert float(lo) == 0.0
    assert 0 < float(hi) < 1


def test_wilson_zero_trials_nan():
    lo, hi = wilson_ci(0, 0)
    assert np.isnan(lo) and np.isnan(hi)


def test_wilson_bounds_in_unit_interval():
    k = np.array([0, 1, 5, 50, 99, 100])
    lo, hi = wilson_ci(k, np.full(6, 100))
    assert (lo >= 0).all() and (hi <= 1).all() and (lo <= hi).all()
    p = k / 100
    # float rounding: k=0, n=100 gives low ~3e-18 rather than exactly 0
    assert (lo <= p + 1e-12).all() and (p <= hi + 1e-12).all()


def test_add_rate_columns_and_zero_den():
    df = pd.DataFrame({"k": [10, 0], "n": [100, 0]})
    out = add_rate(df, "r", "k", "n")
    assert out.loc[0, "r"] == 0.1
    assert np.isnan(out.loc[1, "r"]) and np.isnan(out.loc[1, "r_lo"])
