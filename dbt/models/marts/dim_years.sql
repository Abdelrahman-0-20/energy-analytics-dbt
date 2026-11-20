-- Year spine, 1900 .. latest year in the warehouse: gives every mart a
-- decade axis and a place to hang future calendar attributes.
with spine as (

    select unnest(generate_series(1900, (select max(year) from {{ ref('stg_energy') }}))) as year

)

select
    cast(year as integer)                       as year,
    cast(year - (year % 10) as integer)         as decade,
    cast(year - (year % 10) as varchar) || 's'  as decade_label

from spine
