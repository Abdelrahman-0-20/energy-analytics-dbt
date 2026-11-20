"""Prove the claim every pipeline makes but few prove: rerunning changes nothing.

Snapshots every staging/marts row count, runs `dbt build` a second time, and
exits non-zero if any table's row count moved. CI runs this after its own
build; you can run it locally too:

    python scripts/prove_idempotency.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = REPO_ROOT / "warehouse" / "energy.duckdb"
SCHEMAS = ("staging", "marts")


def find_dbt() -> str:
    found = shutil.which("dbt")
    if found:
        return found
    venv_dbt = REPO_ROOT / ".venv" / "bin" / "dbt"
    if venv_dbt.exists():
        return str(venv_dbt)
    raise SystemExit("dbt not found — pip install -r requirements.txt")


def row_counts() -> dict[str, int]:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        placeholders = ", ".join("?" for _ in SCHEMAS)
        tables = [
            r[0]
            for r in con.execute(
                f"select table_schema || '.' || table_name from information_schema.tables "
                f"where table_schema in ({placeholders}) order by 1",
                list(SCHEMAS),
            ).fetchall()
        ]
        return {t: con.execute(f"select count(*) from {t}").fetchone()[0] for t in tables}
    finally:
        con.close()


def main() -> int:
    before = row_counts()
    cmd = [find_dbt(), "build", "--project-dir", "dbt", "--profiles-dir", "dbt"]
    print(f"[idempotency] snapshot taken ({len(before)} tables); running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stdout.write(proc.stdout[-4000:])
        sys.stderr.write(proc.stderr[-4000:])
        return proc.returncode

    after = row_counts()
    moved = {
        k: {"before": before.get(k), "after": after.get(k)}
        for k in sorted(set(before) | set(after))
        if before.get(k) != after.get(k)
    }
    if moved:
        print(f"[idempotency] FAIL — row counts changed: {moved}", file=sys.stderr)
        return 1
    print(f"[idempotency] PASS — {len(after)} tables unchanged across a full rerun:")
    for table, count in after.items():
        print(f"    {table}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
