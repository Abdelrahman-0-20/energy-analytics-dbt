-- Reference rows without a UN M49 region must match the vetted allow-list.
-- On the pinned release exactly two rows are unclassified; if a third appears,
-- this test fails and the list in this file must be reviewed deliberately.
select
    country_name,
    iso_alpha3
from {{ ref('stg_countries') }}
where region is null
  and country_name not in ('Antarctica', 'Taiwan, Province of China')
