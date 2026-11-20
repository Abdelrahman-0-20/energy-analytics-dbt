with long_source as (

    select * from {{ ref('int_energy_long') }}

),

entities as (

    select * from {{ ref('dim_entities') }}

),

years as (

    select * from {{ ref('dim_years') }}

)

-- Long-form energy mix: the base table for stacked-area and share charts.
-- Entity-years where a source reports nothing at all are dropped.
select
    {{ dbt_utils.generate_surrogate_key(['l.entity_name', 'l.year', 'l.energy_source']) }} as entity_year_source_sk,
    l.entity_name,
    l.year,
    y.decade,
    l.energy_source,
    l.consumption_twh,
    l.electricity_twh,
    l.share_of_energy_pct,
    l.share_of_electricity_pct,
    d.entity_type,
    d.region,
    d.sub_region

from long_source l
left join entities d
    on d.entity_name = l.entity_name
left join years y
    on y.year = l.year
where l.consumption_twh is not null
   or l.electricity_twh is not null
