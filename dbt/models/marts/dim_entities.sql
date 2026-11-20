with source_entities as (

    select distinct entity_name, iso_code
    from {{ ref('stg_energy') }}

),

classified as (

    select
        entity_name,
        iso_code,
        case
            when iso_code is not null
                then 'country'
            when entity_name in ({{ sql_string_list(var('historical_states')) }})
                then 'historical_state'
            when entity_name in ({{ sql_string_list(var('sovereign_without_iso')) }})
                then 'country'
            else 'aggregate'
        end as entity_type

    from source_entities

)

-- Entity dimension: every entity OWID ships, classified. The curated lists
-- live in dbt_project.yml vars — data, not code.
select
    c.entity_name,
    c.iso_code,
    c.entity_type,
    (c.entity_type = 'aggregate')       as is_aggregate,
    r.region,
    r.sub_region

from classified c
left join {{ ref('stg_countries') }} r
    on r.iso_alpha3 = c.iso_code
