"""Load config/assumptions.yaml. The only place the analysis reads its assumptions from."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "assumptions.yaml"
SQL_DIR = ROOT / "sql"
PROCESSED_DIR = ROOT / "data" / "processed"
TABLES_DIR = ROOT / "reports" / "tables"
FIGURES_DIR = ROOT / "reports" / "figures"
DOCS_DIR = ROOT / "docs"

SPEND_MODELS = {"per_session", "revenue_share", "fixed_monthly", "none"}


def load_config(path: Path | str = CONFIG_PATH) -> dict[str, Any]:
    """Read the assumptions file and check that every channel has a known spend model."""
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    for name, ch in cfg["channels"].items():
        if ch.get("model") not in SPEND_MODELS:
            raise ValueError(f"Channel {name!r} has unknown spend model {ch.get('model')!r}")
    return cfg
