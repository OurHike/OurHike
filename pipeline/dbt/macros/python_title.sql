{#-
    Python's str.title() and str.isupper(), for export_nearby_poi.py's
    compose_description(), which title-cases an asset value DEC or USFS
    writes in capitals ('LEAN-TO' is 'Lean-To', 'OBSERVATION SITE' is
    'Observation Site') and leaves OPRHP's own casing alone ('Lean-to').

    title(): a character is upper-cased where the character before it is not
    a cased letter, and lower-cased where it is, judged on the original text,
    as CPython's do_title() judges it. Cased is read as "changes under upper()
    or lower()", which is Python's own test for the letters these layers use.
-#}
{% macro python_title(text) -%}
    array_to_string(
        list_transform(
            range(1, length({{ text }}) + 1),
            lambda position: case
                when
                    position > 1
                    and (
                        upper(substr({{ text }}, position - 1, 1)) != substr({{ text }}, position - 1, 1)
                        or lower(substr({{ text }}, position - 1, 1)) != substr({{ text }}, position - 1, 1)
                    )
                    then lower(substr({{ text }}, position, 1))
                else upper(substr({{ text }}, position, 1))
            end
        ),
        ''
    )
{%- endmacro %}

{#- isupper(): at least one cased character, and none of them lower case. -#}
{% macro python_isupper(text) -%}
    ({{ text }} = upper({{ text }}) and {{ text }} != lower({{ text }}))
{%- endmacro %}
