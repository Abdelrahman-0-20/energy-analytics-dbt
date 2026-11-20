-- Guards the classic silent failure: a truncated or partial upstream file.
-- The pinned release ships 220 distinct countries; anything below
-- {{ var('min_countries') }} means a bad load, not a data story.
select *
from (
    select count(distinct iso_code) as countries_seen
    from {{ ref('stg_energy') }}
    where iso_code is not null
) coverage
where countries_seen < {{ var('min_countries') }}
