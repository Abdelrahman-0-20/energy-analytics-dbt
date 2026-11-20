{{ config(
    materialized='incremental',
    unique_key='entity_year_sk',
    on_schema_change='sync_all_columns'
) }}

-- Gold fact: one row per entity-year. Only the columns a consumer actually
-- asks for — the full 130-col wide table stays in staging.
-- Incremental on year: a new upstream release merges only its new years;
-- history revisions are picked up with `dbt run --full-refresh`.
with energy as (

    select * from {{ ref('stg_energy') }}

),

entities as (

    select * from {{ ref('dim_entities') }}

),

years as (

    select * from {{ ref('dim_years') }}

),

joined as (

    select
        {{ dbt_utils.generate_surrogate_key(['e.entity_name', 'e.year']) }} as entity_year_sk,
        e.entity_name,
        e.iso_code,
        d.entity_type,
        d.region,
        d.sub_region,
        e.year,
        y.decade,
        e.population,
        e.gdp,
        e.primary_energy_consumption,
        e.electricity_generation,
        e.electricity_demand,
        e.energy_per_capita,
        e.carbon_intensity_elec,
        e.greenhouse_gas_emissions,
        e.renewables_share_energy,
        e.low_carbon_share_energy,
        e.fossil_share_energy,
        e.coal_consumption,
        e.oil_consumption,
        e.gas_consumption,
        e.nuclear_consumption,
        e.hydro_consumption,
        e.wind_consumption,
        e.solar_consumption,
        e.biofuel_consumption,
        e.other_renewable_consumption,
        e._ingested_at                              as source_ingested_at

    from energy e
    left join entities d
        on d.entity_name = e.entity_name
    left join years y
        on y.year = e.year

)

select * from joined
{% if is_incremental() %}
where year > (select coalesce(max(year), {{ var('first_energy_year') }} - 1) from {{ this }})
{% endif %}
