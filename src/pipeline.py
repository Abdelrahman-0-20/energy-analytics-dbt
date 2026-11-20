"""Run the whole load side of the pipeline: fetch -> raw tables in DuckDB.

Usage:
    python -m src.pipeline              # fetch (idempotent) then load
    python -m src.pipeline --skip-fetch # offline: load whatever is in data/raw/
"""
from __future__ import annotations

import sys

from . import fetch, load


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    skip_fetch = "--skip-fetch" in argv

    if skip_fetch:
        print("[pipeline] fetch skipped (--skip-fetch)")
    else:
        try:
            for key, status in fetch.fetch_all().items():
                print(f"[fetch] {key}: {status}")
        except fetch.FetchError as exc:
            print(f"[fetch] ERROR: {exc}", file=sys.stderr)
            return 1

    try:
        rows = load.load_all()
    except (load.SchemaContractError, load.EmptySourceError) as exc:
        print(f"[load] ERROR: {exc}", file=sys.stderr)
        return 1

    for row in rows:
        print(
            f"[load] {row['table']}: {row['rows']} rows x {row['columns']} cols "
            f"(sha={row['sha256'][:12]}…, log={row['log']})"
        )
    print(f"[pipeline] done: {len(rows)} raw tables ready for dbt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
