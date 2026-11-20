-- Every ISO code carried in the warehouse must exist in the reference data —
-- except codes withdrawn from ISO 3166-1, which are vetted in dbt_project.yml
-- (currently ANT: Netherlands Antilles, dissolved 2010, kept by OWID for history).
select distinct
    entity_name,
    iso_code
from {{ ref('fct_energy_year') }}
where iso_code is not null
  and iso_code not in (select iso_alpha3 from {{ ref('stg_countries') }})
  and iso_code not in ({{ sql_string_list(var('retired_iso_codes')) }})
