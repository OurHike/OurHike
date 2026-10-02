{#-
    What GDAL's GeoJSON driver writes for a value, read back as json.loads
    reads it. export_poi.py writes the poi_<type>.geojson files with DuckDB's
    `COPY ... (FORMAT GDAL, DRIVER 'GeoJSON')`, and those files are the shape
    a phone reads today (decision 44 makes it v1), so the dbt writer gives
    each value the one a phone parses out of GDAL's text. They go with the
    6-decimal sibling key decision 8 plans for these files.

    GDAL does not print a double exactly. Measured 2026-10-02 on 182,408
    doubles written through that COPY: 60,301 read back as a different double,
    among them -73.99000000000001 as -73.99 and 34.626618000000006 as
    34.626618. Most were coordinates one to three ulps from a 5-to-7-decimal
    value, the shape a reprojected ArcGIS coordinate takes. The two number
    macros below agreed with GDAL on all 182,408, on Python's DuckDB 1.5.5
    and on dbt 2.0.6's bundled 1.5.4. They are GDAL's two code paths, read
    off its output: a DOUBLE property and a coordinate print differently.
-#}

{#-
    A DOUBLE property: GDAL's OGR_json_double_with_significant_figures_to_string
    at its default of -1 significant figures. %.17g, and where the text after
    the decimal point holds a run of six 0s or six 9s, the first of %.16g,
    %.15g and %.14g whose text has a point and no such run, else %.17g.
-#}
{% macro gdal_geojson_double(value) -%}
    {%- set g17 = "printf('%.17g', " ~ value ~ ")" -%}
    cast(
        case
            when
                strpos({{ g17 }}, '.') > 0
                and (
                    contains(substr({{ g17 }}, strpos({{ g17 }}, '.')), '000000')
                    or contains(substr({{ g17 }}, strpos({{ g17 }}, '.')), '999999')
                )
                then coalesce(
                    list_filter(
                        [printf('%.16g', {{ value }}), printf('%.15g', {{ value }}), printf('%.14g', {{ value }})],
                        lambda candidate: strpos(candidate, '.') > 0
                        and not contains(substr(candidate, strpos(candidate, '.')), '000000')
                        and not contains(substr(candidate, strpos(candidate, '.')), '999999')
                    )[1],
                    {{ g17 }}
                )
            else {{ g17 }}
        end as double
    )
{%- endmacro %}

{#- One character of GDAL's text, counted from its end the way ogrutils.cpp counts: s[len - k]. -#}
{% macro _gdal_char_from_end(text, k) -%}
    substr({{ text }}, length({{ text }}) - {{ k }} + 1, 1)
{%- endmacro %}

{#- GDAL's roundup(): one added to the last kept digit, away from zero, in decimal arithmetic. -#}
{% macro _gdal_round_up(kept) -%}
    cast(cast(
        cast({{ kept }} as decimal(38, 15))
        + (case when starts_with({{ kept }}, '-') then -1 else 1 end)
        * cast(pow(10, -(length({{ kept }}) - strpos({{ kept }}, '.'))) as decimal(38, 15))
        as varchar) as double)
{%- endmacro %}

{#-
    A coordinate: GDAL's OGR_json_double_with_precision_to_string at the
    default precision, which is %.15f passed through ogrutils.cpp's
    intelliround(). That trims a trailing run of five 0s before the last
    digit, or eight digits where the run sits further in, and rounds a
    trailing run of five 9s up at the sixth or ninth digit from the end.
    `before` is GDAL's nCountBeforeDot: the digits before the point less one,
    less one more for a minus sign.
-#}
{% macro gdal_geojson_coordinate(value) -%}
    {%- set text = "printf('%.15f', " ~ value ~ ")" -%}
    {%- set n = "length(" ~ text ~ ")" -%}
    {%- set before = "(strpos(" ~ text ~ ", '.') - 2 - (case when starts_with(" ~ text ~ ", '-') then 1 else 0 end))" -%}
    {%- set dot = "(strpos(" ~ text ~ ", '.') - 1)" -%}
    (
        case
            when {{ n }} <= 10 or strpos({{ text }}, '.') = 0 then cast({{ text }} as double)
            when
                {{ _gdal_char_from_end(text, 2) }} = '0' and {{ _gdal_char_from_end(text, 3) }} = '0'
                and {{ _gdal_char_from_end(text, 4) }} = '0' and {{ _gdal_char_from_end(text, 5) }} = '0'
                and {{ _gdal_char_from_end(text, 6) }} = '0'
                then cast(left({{ text }}, {{ n }} - 1) as double)
            when
                {{ dot }} < {{ n }} - 8
                and ({{ before }} >= 4 or {{ _gdal_char_from_end(text, 3) }} = '0')
                and ({{ before }} >= 5 or {{ _gdal_char_from_end(text, 4) }} = '0')
                and ({{ before }} >= 6 or {{ _gdal_char_from_end(text, 5) }} = '0')
                and ({{ before }} >= 7 or {{ _gdal_char_from_end(text, 6) }} = '0')
                and ({{ before }} >= 8 or {{ _gdal_char_from_end(text, 7) }} = '0')
                and {{ _gdal_char_from_end(text, 8) }} = '0' and {{ _gdal_char_from_end(text, 9) }} = '0'
                then cast(left({{ text }}, {{ n }} - 8) as double)
            when
                {{ _gdal_char_from_end(text, 2) }} = '9' and {{ _gdal_char_from_end(text, 3) }} = '9'
                and {{ _gdal_char_from_end(text, 4) }} = '9' and {{ _gdal_char_from_end(text, 5) }} = '9'
                and {{ _gdal_char_from_end(text, 6) }} = '9'
                then {{ _gdal_round_up("left(" ~ text ~ ", " ~ n ~ " - 6)") }}
            when
                {{ dot }} < {{ n }} - 9
                and ({{ before }} >= 4 or {{ _gdal_char_from_end(text, 3) }} = '9')
                and ({{ before }} >= 5 or {{ _gdal_char_from_end(text, 4) }} = '9')
                and ({{ before }} >= 6 or {{ _gdal_char_from_end(text, 5) }} = '9')
                and ({{ before }} >= 7 or {{ _gdal_char_from_end(text, 6) }} = '9')
                and ({{ before }} >= 8 or {{ _gdal_char_from_end(text, 7) }} = '9')
                and {{ _gdal_char_from_end(text, 8) }} = '9' and {{ _gdal_char_from_end(text, 9) }} = '9'
                then {{ _gdal_round_up("left(" ~ text ~ ", " ~ n ~ " - 9)") }}
            else cast({{ text }} as double)
        end
    )
{%- endmacro %}

{#-
    A VARCHAR property as GDAL writes it: its AUTODETECT_JSON_STRINGS, on by
    default, writes a string that starts with [ and ends with ], or starts
    with { and ends with }, and parses as JSON, as that JSON rather than as a
    string. Measured 2026-10-02: '{"a": 1}' was written as an object and
    "[not json" stayed a string. export_poi.py relies on it for `nearby` and
    `photos`, which it stores as JSON text, and it applies to every string
    column alike.
-#}
{% macro gdal_geojson_string(value) -%}
    case
        when
            (
                (left({{ value }}, 1) = '[' and right({{ value }}, 1) = ']')
                or (left({{ value }}, 1) = '{' and right({{ value }}, 1) = '}')
            )
            and json_valid({{ value }})
            then cast({{ value }} as json)
        else to_json({{ value }})
    end
{%- endmacro %}
