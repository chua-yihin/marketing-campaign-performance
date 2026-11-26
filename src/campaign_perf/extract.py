"""Run sql/01-05 in BigQuery (dry run first, byte cap enforced) and write data/processed/*.parquet.

Then reconcile the extracts with 05_validation.sql: sessions, users, transactions and revenue
must agree within the configured tolerance, or the extract fails.
"""

from __future__ import annotations

import pandas as pd

from campaign_perf.bq import GB, render_sql, run_query
from campaign_perf.config import PROCESSED_DIR, TABLES_DIR, load_config

EXTRACTS = {
    "01_user_first_touch.sql": "user_first_touch.parquet",
    "02_user_milestones.sql": "user_milestones.parquet",
    "03_user_activity_days.sql": "user_activity_days.parquet",
    "04_cohort_revenue.sql": "cohort_revenue.parquet",
}
RECONCILE_TOLERANCE = 0.005  # 0.5%
MAX_PARQUET_MB = 50


def to_portable(df: pd.DataFrame) -> pd.DataFrame:
    """Convert BigQuery-only dtypes (dbdate) to plain datetime64 so the parquet files
    read back with pandas alone, without db-dtypes installed."""
    out = df.copy()
    for col in out.columns:
        if str(out[col].dtype) == "dbdate":
            out[col] = pd.to_datetime(out[col].astype(str))
    return out


def reconcile(users: pd.DataFrame, validation: pd.DataFrame) -> pd.DataFrame:
    """Compare totals rebuilt from the user-level extract with the source totals."""
    v = validation.iloc[0]
    rows = [
        ("sessions", float(v["sessions"]), float(users["n_sessions"].sum())),
        ("users", float(v["users"]), float(len(users))),
        ("transactions", float(v["transactions"]), float(users["n_transactions"].sum())),
        ("revenue_usd", float(v["revenue_usd"]), float(users["revenue_usd"].sum())),
    ]
    out = pd.DataFrame(rows, columns=["metric", "source_sql", "parquet"])
    out["rel_diff"] = (out["parquet"] - out["source_sql"]).abs() / out["source_sql"]
    out["ok"] = out["rel_diff"] <= RECONCILE_TOLERANCE
    return out


def main() -> None:
    cfg = load_config()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    log = []

    frames = {}
    for sql_name, out_name in EXTRACTS.items():
        df, nbytes = run_query(render_sql(sql_name, cfg), sql_name, cfg)
        path = PROCESSED_DIR / out_name
        to_portable(df).to_parquet(path, index=False)
        mb = path.stat().st_size / 1024**2
        if mb > MAX_PARQUET_MB:
            raise RuntimeError(f"{out_name} is {mb:.1f} MB, over the {MAX_PARQUET_MB} MB limit")
        print(f"  -> {path.name}: {len(df):,} rows, {mb:.1f} MB")
        log.append({"query": sql_name, "gb_processed": nbytes / GB, "rows": len(df)})
        frames[sql_name] = df

    validation, nbytes = run_query(render_sql("05_validation.sql", cfg), "05_validation", cfg)
    validation.to_csv(TABLES_DIR / "validation_source_totals.csv", index=False, lineterminator="\n")
    log.append({"query": "05_validation.sql", "gb_processed": nbytes / GB, "rows": len(validation)})
    pd.DataFrame(log).to_csv(TABLES_DIR / "extract_bytes.csv", index=False, lineterminator="\n")

    rec = reconcile(frames["01_user_first_touch.sql"], validation)
    rec.to_csv(TABLES_DIR / "reconciliation.csv", index=False, lineterminator="\n")
    print(rec.to_string(index=False))
    if not rec["ok"].all():
        raise SystemExit("Reconciliation failed: extract totals differ from source by > 0.5%")
    print(f"Total processed: {sum(r['gb_processed'] for r in log):.2f} GB")


if __name__ == "__main__":
    main()
