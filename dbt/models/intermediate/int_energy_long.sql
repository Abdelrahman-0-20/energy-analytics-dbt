{#-
    Wide -> long: one row per (entity, year, energy source).
    Generated from macros/source_metric_map() so the naming trap upstream
    (other_renewable_* vs other_renewables_*) lives in exactly one place.
-#}
{% set metric_map = source_metric_map() %}
{% for source_name, cols in metric_map.items() %}

select
    entity_name,
    year,
    '{{ source_name }}'                         as energy_source,
    {{ cols['consumption'] }}                   as consumption_twh,
    {{ cols['electricity'] }}                   as electricity_twh,
    {{ cols['share_energy'] }}                  as share_of_energy_pct,
    {{ cols['share_elec'] }}                    as share_of_electricity_pct

from {{ ref('stg_energy') }}
{% if not loop.last %}union all{% endif %}
{% endfor %}
