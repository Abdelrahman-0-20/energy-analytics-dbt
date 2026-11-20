with country_series as (

    -- Only real countries: aggregates (World, regions, income groups) would
    -- double-count the very countries they summarise.
    select
        d.entity_name,
        d.region,
        d.sub_region,
        e.year,
        e.renewables_share_energy
    from {{ ref('stg_energy') }} e
    join {{ ref('dim_entities') }} d
        on d.entity_name = e.entity_name
    where d.entity_type = 'country'
      and e.renewables_share_energy is not null

),

latest as (

    select * from country_series
    qualify row_number() over (partition by entity_name order by year desc) = 1

),

baseline as (

    -- first year each country actually reports a renewables share
    select * from country_series
    qualify row_number() over (partition by entity_name order by year asc) = 1

)

select
    l.entity_name,
    l.region,
    l.sub_region,
    b.year                                          as baseline_year,
    b.renewables_share_energy                       as baseline_renewables_share_pct,
    l.year                                          as latest_year,
    l.renewables_share_energy                       as latest_renewables_share_pct,
    round(l.renewables_share_energy - b.renewables_share_energy, 2) as change_pp,
    rank() over (order by l.renewables_share_energy desc)           as renewables_rank

from latest l
join baseline b
    on b.entity_name = l.entity_name
