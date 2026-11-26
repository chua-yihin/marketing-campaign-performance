"""BigQuery helpers: every query is dry-run first and capped at the configured byte budget."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from campaign_perf.config import SQL_DIR, load_config

GB = 1024**3


def render_sql(name: str, cfg: dict) -> str:
    """Read sql/<name> and fill the date-range placeholders from config."""
    text = (SQL_DIR / name).read_text(encoding="utf-8")
    start = cfg["data"]["start_date"].replace("-", "")
    end = cfg["data"]["end_date"].replace("-", "")
    return text.replace("{start_suffix}", start).replace("{end_suffix}", end)


def run_query(sql: str, label: str, cfg: dict | None = None) -> tuple[pd.DataFrame, int]:
    """Dry-run, refuse anything over the cap, then run with maximum_bytes_billed set.

    Returns the result and the bytes processed reported by the dry run.
    """
    from google.cloud import bigquery

    cfg = cfg or load_config()
    cap = int(cfg["data"]["max_bytes_per_query_gb"] * GB)
    client = bigquery.Client(project=cfg["data"]["billing_project"])

    dry = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
    nbytes = dry.total_bytes_processed
    print(f"[dry run] {label}: {nbytes / GB:.2f} GB processed (cap {cap / GB:.0f} GB)")
    if nbytes > cap:
        raise RuntimeError(f"{label} would process {nbytes / GB:.2f} GB, over the cap; refusing")

    job = client.query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=cap))
    df = job.to_dataframe()
    billed = job.total_bytes_billed or 0
    print(f"[run] {label}: {len(df):,} rows, {billed / GB:.2f} GB billed")
    return df, nbytes


def run_sql_file(name: str, cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config()
    df, _ = run_query(render_sql(name, cfg), Path(name).stem, cfg)
    return df
