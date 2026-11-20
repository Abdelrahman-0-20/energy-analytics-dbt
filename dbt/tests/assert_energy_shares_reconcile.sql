-- Source consumptions must reconcile with OWID's reported primary energy.
-- Scope: entity-years where all nine sources report (6,379 on the pinned
-- release); measured ratio min 95.6%, max 102.9%, 0 rows outside +/-5%.
with per_entity_year as (

    select
        entity_name,
        year,
        coal_consumption + oil_consumption + gas_consumption + nuclear_consumption +
        hydro_consumption + wind_consumption + solar_consumption + biofuel_consumption +
        other_renewable_consumption                    as sum_sources_twh,
        primary_energy_consumption                     as primary_twh
    from {{ ref('stg_energy') }}
    where primary_energy_consumption > 0

)

select
    entity_name,
    year,
    sum_sources_twh,
    primary_twh,
    round(100.0 * sum_sources_twh / primary_twh, 1)    as pct_of_reported
from per_entity_year
where sum_sources_twh is not null
  and abs(sum_sources_twh - primary_twh)
      > ({{ var('reconcile_tolerance_pct') }} / 100.0) * primary_twh
