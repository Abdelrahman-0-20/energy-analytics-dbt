{% test expect_value_between(model, column_name, min_value=none, max_value=none, row_condition=none) %}
    {#-
        Rows where column_name falls outside [min_value, max_value].
        NULLs are skipped on purpose: sparse metrics (gdp, early-year shares)
        are legitimate, absence is not an error. Requires at least one bound.
    -#}
    {%- if min_value is none and max_value is none -%}
        {{ exceptions.raise_compiler_error("expect_value_between needs min_value and/or max_value") }}
    {%- endif -%}

select *
from {{ model }}
where {{ column_name }} is not null
    {%- if row_condition %}
    and ({{ row_condition }})
    {%- endif %}
    {%- if min_value is not none %}
    and {{ column_name }} < {{ min_value }}
    {%- endif %}
    {%- if max_value is not none %}
    and {{ column_name }} > {{ max_value }}
    {%- endif %}
{% endtest %}
