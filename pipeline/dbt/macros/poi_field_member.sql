{#-
    The JSON member a source field lands under in int_points_of_interest__
    unioned's `properties`: dlt's sql_ci naming lowercases every column, so
    sources.json's `OBJECTID` is `objectid` and `Sub_Asset` is `sub_asset`.
    Socrata's row id `:id` is the one exception, landed as `_socrata_id`
    (extract/_kinds.py's SocrataDataset). `field` is a SQL expression that
    holds the field's name; a null name is a null member, which reads nothing.
-#}
{% macro poi_field_member(field) -%}
    (case when {{ field }} = ':id' then '_socrata_id' else lower({{ field }}) end)
{%- endmacro %}
