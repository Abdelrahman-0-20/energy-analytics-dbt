"""Export the dashboard's gold marts to dashboard/data/*.csv.

Streamlit Community Cloud has no warehouse (warehouse/*.duckdb is gitignored —
it is a build artifact). CI runs this after dbt build and commits the CSVs
back with [skip ci], so the deployed app always has data. Locally the app
prefers the live warehouse and falls back to these CSVs.

    python -m src.export_marts
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

from .fetch import REPO_ROOT, load_config
from .mart_queries import QUERIES

EXPORT_DIR = REPO_ROOT / "dashboard" / "data"


def export(con: duckdb.DuckDBPyConnection, export_dir: Path = EXPORT_DIR) -> dict[str, int]:
    export_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for name, sql in QUERIES.items():
        df = pd.read_sql(sql, con)
        path = export_dir / f"{name}.csv"
        df.to_csv(path, index=False)
        counts[name] = len(df)
    return counts


def main(argv: list[str] | None = None) -> int:
    cfg = load_config()
    warehouse = (argv or sys.argv[1:] or [str(REPO_ROOT / cfg["paths"]["warehouse"])])[0]
    if not Path(warehouse).exists():
        print(
            f"[export] ERROR: warehouse not found at {warehouse} — "
            "run: python -m src.pipeline && dbt build --project-dir dbt --profiles-dir dbt",
            file=sys.stderr,
        )
        return 1
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        counts = export(con)
    finally:
        con.close()
    for name, n in counts.items():
        print(f"[export] dashboard/data/{name}.csv: {n} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
