"""Load raw CSVs into DuckDB: faithful, contract-checked, deterministic.

Design:
  * raw tables are rebuilt with CREATE OR REPLACE from the files on disk, so a
    re-run produces byte-identical tables (idempotent by construction);
  * audit columns come from ingest_log, which records each (source, file,
    sha256) once — _ingested_at therefore never changes on a re-run either;
  * the loader FAILS LOUD when a required column disappears: schema drift must
    alert, never silently corrupt downstream models.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from .fetch import REPO_ROOT, load_config, sha256_file, sources_from_config, Source


class SchemaContractError(RuntimeError):
    """A source file no longer satisfies the contract in config.yaml."""

    def __init__(self, source_key: str, missing: list[str], found: list[str]):
        self.source_key = source_key
        self.missing = missing
        self.found = found
        super().__init__(
            f"source '{source_key}' no longer satisfies its data contract — "
            f"missing columns: {', '.join(missing)}"
        )


class EmptySourceError(RuntimeError):
    """An upstream source came back with zero rows."""


def check_contract(columns: list[str], required: list[str]) -> list[str]:
    """Return the required columns absent from the file's header."""
    present = set(columns)
    return [c for c in required if c not in present]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def ensure_ingest_log(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ingest_log (
            source       VARCHAR NOT NULL,
            file         VARCHAR NOT NULL,
            url          VARCHAR NOT NULL,
            sha256       VARCHAR NOT NULL,
            row_count    BIGINT  NOT NULL,
            column_count BIGINT  NOT NULL,
            ingested_at  TIMESTAMP NOT NULL,
            PRIMARY KEY (source, file)
        )
        """
    )


def upsert_ingest_log(
    con: duckdb.DuckDBPyConnection,
    *,
    source_key: str,
    file_name: str,
    url: str,
    sha256: str,
    row_count: int,
    column_count: int,
    ingested_at: datetime | None = None,
) -> str:
    """Record an ingest once per (source, file). Unchanged content keeps its
    original ingested_at so re-runs stay byte-identical.

    Returns 'inserted' | 'updated' | 'unchanged'.
    """
    ensure_ingest_log(con)
    row = con.execute(
        "SELECT sha256 FROM ingest_log WHERE source = ? AND file = ?",
        [source_key, file_name],
    ).fetchone()
    if row is None:
        con.execute(
            "INSERT INTO ingest_log (source, file, url, sha256, row_count, column_count, ingested_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [source_key, file_name, url, sha256, row_count, column_count, ingested_at or _utc_now()],
        )
        return "inserted"
    if row[0] == sha256:
        return "unchanged"
    con.execute(
        "UPDATE ingest_log SET url = ?, sha256 = ?, row_count = ?, column_count = ?, ingested_at = ? "
        "WHERE source = ? AND file = ?",
        [url, sha256, row_count, column_count, ingested_at or _utc_now(), source_key, file_name],
    )
    return "updated"


def table_name_for(source_key: str) -> str:
    return f"raw_{source_key}"


def load_source(
    con: duckdb.DuckDBPyConnection,
    source: Source,
    required: list[str],
    *,
    root: Path = REPO_ROOT,
) -> dict:
    """Contract-check one CSV, then rebuild its raw_* table deterministically."""
    ensure_ingest_log(con)
    path = root / source.file if not source.file.is_absolute() else source.file

    columns = [r[0] for r in con.execute("DESCRIBE SELECT * FROM read_csv_auto(?)", [str(path)]).fetchall()]
    missing = check_contract(columns, required)
    if missing:
        raise SchemaContractError(source.key, missing, columns)

    row_count = con.execute("SELECT count(*) FROM read_csv_auto(?)", [str(path)]).fetchone()[0]
    if row_count == 0:
        raise EmptySourceError(f"source '{source.key}' ({path.name}) has zero rows; refusing to load")

    sha = sha256_file(path)
    log_state = upsert_ingest_log(
        con,
        source_key=source.key,
        file_name=path.name,
        url=source.url,
        sha256=sha,
        row_count=row_count,
        column_count=len(columns),
    )

    table = table_name_for(source.key)
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {table} AS
        SELECT src.*, log.sha256 AS _source_sha256, log.ingested_at AS _ingested_at
        FROM read_csv_auto(?) src
        JOIN ingest_log log ON log.source = ? AND log.file = ?
        """,
        [str(path), source.key, path.name],
    )
    return {
        "source": source.key,
        "table": table,
        "rows": row_count,
        "columns": len(columns),
        "sha256": sha,
        "log": log_state,
    }


def load_all(
    config: dict | None = None,
    *,
    con: duckdb.DuckDBPyConnection | None = None,
    root: Path = REPO_ROOT,
    warehouse: str | None = None,
) -> list[dict]:
    """Load every configured source. Opens the warehouse when no connection is given."""
    cfg = config if config is not None else load_config()
    owns_con = con is None
    if owns_con:
        db_path = warehouse or str(root / cfg["paths"]["warehouse"])
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(db_path)
    try:
        summary = []
        for source in sources_from_config(cfg, root=root):
            required = cfg["sources"][source.key].get("required_columns", [])
            summary.append(load_source(con, source, required, root=root))
        return summary
    finally:
        if owns_con:
            con.close()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cfg = load_config()
    warehouse = argv[0] if argv else None
    try:
        for row in load_all(cfg, warehouse=warehouse):
            print(
                f"[load] {row['table']}: {row['rows']} rows x {row['columns']} cols "
                f"(sha={row['sha256'][:12]}…, log={row['log']})"
            )
    except (SchemaContractError, EmptySourceError) as exc:
        print(f"[load] ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
