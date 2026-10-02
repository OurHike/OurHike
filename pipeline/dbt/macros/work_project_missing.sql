{#-
    lib/work_projects.py's REQUIRED_FIELDS check of one field, for
    int_closures__work_projects_checked (CL17): `field not in row or
    row.get(field) in ("", None)`, so a key that is absent, JSON null, or the
    empty string. Whitespace is not empty there, so it is not here. `name` is
    the stem of the model's <name>_type and <name>_text columns.
-#}
{% macro work_project_missing(name) -%}
    coalesce(
        {{ name }}_type is null
        or {{ name }}_type = 'NULL'
        or ({{ name }}_type = 'VARCHAR' and {{ name }}_text = ''),
        false
    )
{%- endmacro %}
