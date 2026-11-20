-- staging: conformed, typed, and nothing else.
-- The wide source-metric columns are listed explicitly on purpose: this file IS
-- the readable contract between raw and every downstream model.
with source as (

    select * from {{ source('raw', 'raw_energy') }}

)

select
    country                                   as entity_name,
    iso_code,
    cast(year as integer)                    as year,
    population,
    gdp,
    primary_energy_consumption,
    electricity_generation,
    electricity_demand,
    energy_per_capita,
    carbon_intensity_elec,
    greenhouse_gas_emissions,
    renewables_share_energy,
    low_carbon_share_energy,
    fossil_share_energy,
    coal_consumption,
    coal_electricity,
    coal_share_energy,
    coal_share_elec,
    oil_consumption,
    oil_electricity,
    oil_share_energy,
    oil_share_elec,
    gas_consumption,
    gas_electricity,
    gas_share_energy,
    gas_share_elec,
    nuclear_consumption,
    nuclear_electricity,
    nuclear_share_energy,
    nuclear_share_elec,
    hydro_consumption,
    hydro_electricity,
    hydro_share_energy,
    hydro_share_elec,
    wind_consumption,
    wind_electricity,
    wind_share_energy,
    wind_share_elec,
    solar_consumption,
    solar_electricity,
    solar_share_energy,
    solar_share_elec,
    biofuel_consumption,
    biofuel_electricity,
    biofuel_share_energy,
    biofuel_share_elec,
    other_renewable_consumption,
    other_renewable_electricity,
    other_renewables_share_energy,
    other_renewables_share_elec,
    _source_sha256,
    _ingested_at

from source
