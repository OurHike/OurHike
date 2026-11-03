{#-
    Whether a JSON value is truthy the way Python reads the same value out of
    json.loads: null (or absent), false, 0, "", [] and {} are falsy, and
    everything else is truthy. For a Python check written `if not
    block.get(field)`, such as export_sources.py's required support and store
    fields, ported to SQL over the registry's JSON as written.
-#}
{% macro python_truthy(value) -%}
    case coalesce(json_type({{ value }}), 'NULL')
        when 'NULL' then false
        when 'BOOLEAN' then cast({{ value }} as boolean)
        when 'VARCHAR' then json_extract_string({{ value }}, '$') != ''
        when 'ARRAY' then json_array_length({{ value }}) > 0
        when 'OBJECT' then len(json_keys({{ value }})) > 0
        else try_cast(json_extract_string({{ value }}, '$') as double) != 0
    end
{%- endmacro %}

{#-
    The name of the Python type json.loads would give a JSON value, as a
    Python message prints it with `type(value).__name__`.
-#}
{% macro python_type_name(value) -%}
    case coalesce(json_type({{ value }}), 'NULL')
        when 'NULL' then 'NoneType'
        when 'BOOLEAN' then 'bool'
        when 'VARCHAR' then 'str'
        when 'ARRAY' then 'list'
        when 'OBJECT' then 'dict'
        when 'DOUBLE' then 'float'
        else 'int'
    end
{%- endmacro %}
