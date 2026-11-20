"""Energy dashboard — the consumer named in dbt/exposures.yml.

Reads the gold marts ONLY (never staging/raw): every query below is prefixed
with marts., enforced by the exposure's dependency graph.

Run locally:
    streamlit run dashboard/app.py
"""
import os

import duckdb
import pandas as pd
import streamlit as st

WAREHOUSE = os.environ.get("DUCKDB_PATH", "warehouse/energy.duckdb")

st.set_page_config(page_title="Energy Analytics", page_icon="⚡", layout="wide")


@st.cache_resource
def warehouse() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(WAREHOUSE, read_only=True)


@st.cache_data
def query(sql: str) -> pd.DataFrame:
    return pd.read_sql(sql, warehouse())


st.title("Energy Analytics")
st.caption(
    "OWID energy data · dbt gold layer · 1900–2025 · "
    "raw → staging → intermediate → marts"
)

tab_snapshot, tab_transition, tab_mix = st.tabs(
    ["Country snapshot", "Renewable transition", "Energy mix"]
)

with tab_snapshot:
    snapshot = query(
        """
        select entity_name as country, iso_code, region, sub_region,
               latest_year, population, gdp,
               round(primary_energy_consumption, 1) as primary_energy_twh,
               round(energy_per_capita, 0)          as kwh_per_person,
               round(renewables_share_energy, 1)    as renewables_pct,
               round(fossil_share_energy, 1)        as fossil_pct,
               energy_per_capita_rank
        from marts.mart_energy_snapshot
        order by energy_per_capita_rank
        """
    )
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
    transition = query(
        """
        select entity_name as country, region,
               baseline_year, round(baseline_renewables_share_pct, 1) as baseline_pct,
               latest_year, round(latest_renewables_share_pct, 1)     as latest_pct,
               change_pp, renewables_rank
        from marts.mart_renewable_transition
        order by change_pp desc
        """
    )
    st.markdown("**Biggest gains in renewables share** (percentage points, first observation → latest)")
    top = transition.head(15).set_index("country")[["change_pp"]]
    st.bar_chart(top, height=320)
    st.markdown("**Full ranking**")
    st.dataframe(transition, use_container_width=True, hide_index=True, height=320)

with tab_mix:
    countries = query(
        """
        select distinct entity_name as country
        from marts.mart_energy_mix
        where entity_type = 'country'
        order by 1
        """
    )["country"].tolist()
    choice = st.selectbox("Country", countries, index=countries.index("Germany") if "Germany" in countries else 0)
    # country names contain apostrophes (Côte d'Ivoire) — SQL-escape them
    safe = choice.replace("'", "''")
    mix = query(
        f"""
        select year, energy_source, round(consumption_twh, 1) as twh
        from marts.mart_energy_mix
        where entity_name = '{safe}'
          and entity_type = 'country'
          and year >= 1965
        order by year
        """
    )
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
