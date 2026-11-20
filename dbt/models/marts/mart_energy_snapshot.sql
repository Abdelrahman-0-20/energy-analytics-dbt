with latest_per_country as (

    -- latest year each country actually reports (the current year is always
    -- partial upstream: 90 countries in 2025 vs 220 in 2023)
    select *
    from {{ ref('stg_energy') }} e
    where exists (
        select 1 from {{ ref('dim_entities') }} d
        where d.entity_name = e.entity_name
          and d.entity_type = 'country'
    )
    qualify row_number() over (partition by entity_name order by year desc) = 1

)

select
    s.entity_name,
    s.iso_code,
    d.region,
    d.sub_region,
    s.year                                            as latest_year,
    s.population,
    s.gdp,
    s.primary_energy_consumption,
    s.energy_per_capita,
    s.renewables_share_energy,
    s.fossil_share_energy,
    s.carbon_intensity_elec,
    rank() over (order by s.energy_per_capita desc nulls last) as energy_per_capita_rank

from latest_per_country s
join {{ ref('dim_entities') }} d
    on d.entity_name = s.entity_name
