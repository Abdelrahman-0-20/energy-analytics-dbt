-- staging: ISO 3166 reference data, hyphenated source columns made SQL-friendly.
with source as (

    select * from {{ source('raw', 'raw_countries') }}

)

select
    name                                        as country_name,
    "alpha-2"                                   as iso_alpha2,
    "alpha-3"                                   as iso_alpha3,
    cast("country-code" as integer)             as numeric_code,
    region,
    "sub-region"                                as sub_region,
    "intermediate-region"                       as intermediate_region,
    _source_sha256,
    _ingested_at

from source
