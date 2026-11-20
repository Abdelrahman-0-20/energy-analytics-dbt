"""Energy dashboard — the consumer named in dbt/exposures.yml.

Data resolution order:
  1. dashboard/data/*.csv  — committed by CI (works on Streamlit Cloud,
     where warehouse/*.duckdb does not exist because it is gitignored)
  2. the local warehouse    — always fresh after a dbt build
  3. a friendly message     — never a raw traceback

Reads gold marts ONLY (every query lives in src/mart_queries.py, prefixed
with marts.).

Run locally:
    streamlit run dashboard/app.py
"""
import os
import sys
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.mart_queries import QUERIES  # noqa: E402  (single source of truth)

WAREHOUSE = os.environ.get("DUCKDB_PATH", str(REPO_ROOT / "warehouse" / "energy.duckdb"))
DATA_DIR = Path(__file__).resolve().parent / "data"

st.set_page_config(page_title="Energy Analytics", page_icon="⚡", layout="wide")


@st.cache_resource
def warehouse() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(WAREHOUSE, read_only=True)


@st.cache_data
def load(name: str) -> pd.DataFrame:
    """CSV first (deployed), warehouse second (local), never a traceback."""
    csv = DATA_DIR / f"{name}.csv"
    if csv.exists():
        return pd.read_csv(csv)
    try:
        return pd.read_sql(QUERIES[name], warehouse())
    except Exception as exc:  # noqa: BLE001 — show guidance, not a stack trace
        st.error(
            f"No data for {name}: neither dashboard/data/{name}.csv nor the "
            f"warehouse at {WAREHOUSE} is available.\n\n"
            "Build it locally with:\n\n"
            "    python -m src.pipeline && dbt build --project-dir dbt --profiles-dir dbt\n"
            "    python -m src.export_marts"
        )
        st.stop()
        raise  # pragma: no cover — st.stop() raises internally


st.title("Energy Analytics")
st.caption(
    "OWID energy data · dbt gold layer · 1900–2025 · "
    "raw → staging → intermediate → marts"
)

tab_snapshot, tab_transition, tab_mix = st.tabs(
    ["Country snapshot", "Renewable transition", "Energy mix"]
)

with tab_snapshot:
    snapshot = load("snapshot")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Countries", f"{len(snapshot):,}")
    c2.metric(
        "Median renewables share",
        f"{snapshot['renewables_pct'].median():.1f}%",
    )
    c3.metric(
        "Countries >50% renewables",
        f"{int((snapshot['renewables_pct'] > 50).sum())}",
    )
    c4.metric(
        "Latest year covered",
        f"{int(snapshot['latest_year'].max())}",
    )
    st.dataframe(snapshot, use_container_width=True, hide_index=True, height=420)

with tab_transition:
    transition = load("transition")
    st.markdown("**Biggest gains in renewables share** (percentage points, first observation → latest)")
    top = transition.head(15).set_index("country")[["change_pp"]]
    st.bar_chart(top, height=320)
    st.markdown("**Full ranking**")
    st.dataframe(transition, use_container_width=True, hide_index=True, height=320)

with tab_mix:
    mix_all = load("mix")
    countries = sorted(mix_all.loc[mix_all["entity_type"] == "country", "country"].unique())
    choice = st.selectbox(
        "Country", countries, index=countries.index("Germany") if "Germany" in countries else 0
    )
    mix = mix_all[mix_all["country"] == choice]
    if mix.empty:
        st.info(f"No energy-mix history for {choice} before 1965.")
    else:
        pivot = (
            mix.pivot_table(index="year", columns="energy_source", values="twh")
            .sort_index()
            .fillna(0)
        )
        st.markdown(f"**{choice}** — primary energy consumption by source (TWh)")
        st.area_chart(pivot, height=420)
