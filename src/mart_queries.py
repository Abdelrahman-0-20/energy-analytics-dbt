"""The dashboard's queries — one source of truth.

Used by src/export_marts.py (CI writes dashboard/data/*.csv) and by
dashboard/app.py when running locally against the warehouse. The dashboard
reads gold marts only; nothing here touches staging or raw.
"""

QUERIES: dict[str, str] = {
    "snapshot": """
        select entity_name as country, iso_code, region, sub_region,
               latest_year, population, gdp,
               round(primary_energy_consumption, 1) as primary_energy_twh,
               round(energy_per_capita, 0)          as kwh_per_person,
               round(renewables_share_energy, 1)    as renewables_pct,
               round(fossil_share_energy, 1)        as fossil_pct,
               energy_per_capita_rank
        from marts.mart_energy_snapshot
        order by energy_per_capita_rank, country   -- tiebreakers keep the CSV byte-stable
    """,
    "transition": """
        select entity_name as country, region,
               baseline_year, round(baseline_renewables_share_pct, 1) as baseline_pct,
               latest_year, round(latest_renewables_share_pct, 1)     as latest_pct,
               change_pp, renewables_rank
        from marts.mart_renewable_transition
        order by change_pp desc, country           -- deterministic ties
    """,
    "mix": """
        select entity_name as country, entity_type, year, energy_source,
               round(consumption_twh, 1) as twh
        from marts.mart_energy_mix
        where year >= 1965
        order by year, country, energy_source      -- deterministic ties
    """,
}
