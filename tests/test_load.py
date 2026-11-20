"""load: data contract, raw table rebuild, ingest-log idempotency."""
from copy import deepcopy
from pathlib import Path

import duckdb
import pytest

from src.fetch import load_config, Source
from src.load import (
    EmptySourceError,
    SchemaContractError,
    check_contract,
    load_all,
    table_name_for,
)

CFG = load_config()
ENERGY_REQUIRED = CFG["sources"]["energy"]["required_columns"]
COUNTRIES_REQUIRED = CFG["sources"]["countries"]["required_columns"]


def _energy_csv(columns: list[str], rows: list[list[object]]) -> str:
    body = [",".join(columns)]
    for row in rows:
        body.append(",".join("" if v is None else str(v) for v in row))
    return "\n".join(body) + "\n"


def _write_sources(tmp_path: Path, *, drop_energy_column: str | None = None, energy_rows: int = 3) -> dict:
    """Materialise a config whose two sources live in tmp_path, built from the
    real contract so the happy path exercises the production column list."""
    cfg = deepcopy(CFG)
    energy_cols = [c for c in ENERGY_REQUIRED if c != drop_energy_column]

    rows = []
    for i in range(energy_rows):
        row = {c: None for c in energy_cols}
        row.update({"country": f"Country{i}", "year": 2000 + i, "iso_code": f"C0{i}",
                    "population": 1_000_000 + i, "gdp": 1e10, "primary_energy_consumption": 100.0 + i,
                    "coal_consumption": 10.0 + i, "coal_electricity": 5.0 + i,
                    "coal_share_energy": 30.0, "coal_share_elec": 20.0})
        rows.append([row[c] for c in energy_cols])
    (tmp_path / "energy.csv").write_text(_energy_csv(energy_cols, rows), encoding="utf-8")
    (tmp_path / "countries.csv").write_text(
        _energy_csv(COUNTRIES_REQUIRED, [["Country0", "C00", "Europe", "Eastern Europe"],
                                          ["Country1", "C01", "Asia", "Southern Asia"]]),
        encoding="utf-8",
    )
    cfg["sources"]["energy"]["file"] = str(tmp_path / "energy.csv")
    cfg["sources"]["countries"]["file"] = str(tmp_path / "countries.csv")
    return cfg


def test_check_contract_reports_missing_columns() -> None:
    assert check_contract(["country", "year"], ["country", "year", "gdp"]) == ["gdp"]
    assert check_contract(["country"], ["country"]) == []


def test_load_builds_raw_tables_and_logs(tmp_path: Path) -> None:
    cfg = _write_sources(tmp_path)
    con = duckdb.connect(":memory:")
    summary = load_all(cfg, con=con)

    assert {s["table"] for s in summary} == {"raw_energy", "raw_countries"}
    energy = next(s for s in summary if s["table"] == "raw_energy")
    assert energy["rows"] == 3
    assert energy["log"] == "inserted"

    cols = [r[0] for r in con.execute("DESCRIBE raw_energy").fetchall()]
    assert "_ingested_at" in cols and "_source_sha256" in cols
    assert con.execute("SELECT count(*) FROM ingest_log").fetchone()[0] == 2


def test_load_rerun_is_byte_identical(tmp_path: Path) -> None:
    cfg = _write_sources(tmp_path)
    con = duckdb.connect(":memory:")
    first = load_all(cfg, con=con)
    snapshot = con.execute(
        "SELECT source, sha256, ingested_at FROM ingest_log ORDER BY source"
    ).fetchall()
    table_dump = con.execute("SELECT * FROM raw_energy ORDER BY country, year").fetchall()

    second = load_all(cfg, con=con)
    assert [s["log"] for s in second] == ["unchanged", "unchanged"]
    assert con.execute(
        "SELECT source, sha256, ingested_at FROM ingest_log ORDER BY source"
    ).fetchall() == snapshot
    assert con.execute("SELECT * FROM raw_energy ORDER BY country, year").fetchall() == table_dump
    assert [s["rows"] for s in first] == [s["rows"] for s in second]


def test_load_fails_loud_on_schema_drift(tmp_path: Path) -> None:
    cfg = _write_sources(tmp_path, drop_energy_column="primary_energy_consumption")
    con = duckdb.connect(":memory:")
    with pytest.raises(SchemaContractError) as exc:
        load_all(cfg, con=con)
    assert "primary_energy_consumption" in str(exc.value)
    assert exc.value.missing == ["primary_energy_consumption"]
    # nothing should have been built for the failing source
    assert "raw_energy" not in [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables").fetchall()]


def test_load_fails_loud_on_empty_source(tmp_path: Path) -> None:
    cfg = _write_sources(tmp_path, energy_rows=3)
    # empty file with only a header
    cols = [c for c in ENERGY_REQUIRED]
    (tmp_path / "energy.csv").write_text(",".join(cols) + "\n", encoding="utf-8")
    con = duckdb.connect(":memory:")
    with pytest.raises(EmptySourceError, match="zero rows"):
        load_all(cfg, con=con)


def test_table_name_for() -> None:
    assert table_name_for("energy") == "raw_energy"
