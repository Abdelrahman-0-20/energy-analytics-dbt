{% macro generate_schema_name(custom_schema_name, node) -%}
    {#- DuckDB projects usually want plain schema names: 'staging', 'marts'.
        The default macro prefixes them with the target schema (main_staging),
        which is noise in a file-based warehouse. -#}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
