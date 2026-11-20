{% macro sql_string_list(values) %}
    {#- ['a', 'b'] -> "'a','b'" for use in an IN clause. -#}
    {{ return("'" ~ values | join("','") ~ "'") }}
{% endmacro %}

{% macro source_metric_map() %}
    {#-
        source -> the four metric columns we model in the long mart.
        Upstream naming is deliberately inconsistent: 'other_renewable' is
        singular for consumption/electricity but plural ('other_renewables_')
        for the share columns. An explicit map documents the trap, and the
        loader's data contract (config.yaml) keeps it from going stale.
    -#}
    {% set map = {} %}
    {% for source in ['coal', 'oil', 'gas', 'nuclear', 'hydro', 'wind', 'solar', 'biofuel'] %}
        {% do map.update({source: {
            'consumption': source ~ '_consumption',
            'electricity': source ~ '_electricity',
            'share_energy': source ~ '_share_energy',
            'share_elec': source ~ '_share_elec'
        }}) %}
    {% endfor %}
    {% do map.update({'other_renewable': {
        'consumption': 'other_renewable_consumption',
        'electricity': 'other_renewable_electricity',
        'share_energy': 'other_renewables_share_energy',
        'share_elec': 'other_renewables_share_elec'
    }}) %}
    {{ return(map) }}
{% endmacro %}
