"""Small statistics helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

Z95 = 1.959963984540054


def wilson_ci(successes, trials, z: float = Z95) -> tuple[np.ndarray, np.ndarray]:
    """Wilson score interval for a binomial proportion. Returns (low, high); NaN if trials = 0."""
    k = np.asarray(successes, dtype=float)
    n = np.asarray(trials, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = k / n
        denom = 1 + z**2 / n
        centre = (p + z**2 / (2 * n)) / denom
        half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
        low = np.where(n > 0, np.clip(centre - half, 0, 1), np.nan)
        high = np.where(n > 0, np.clip(centre + half, 0, 1), np.nan)
    return low, high


def add_rate(df: pd.DataFrame, name: str, num: str, den: str) -> pd.DataFrame:
    """Add <name>, <name>_lo, <name>_hi columns: num/den with a Wilson 95% CI."""
    out = df.copy()
    n = out[den].to_numpy(dtype=float)
    k = out[num].to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        out[name] = np.where(n > 0, k / n, np.nan)
    out[f"{name}_lo"], out[f"{name}_hi"] = wilson_ci(k, n)
    return out
