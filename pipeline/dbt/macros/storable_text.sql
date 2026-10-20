{#- Text DuckDB cannot store: monthly runs 26 (attempt 1) and 27 (the build
    and all three retries) stopped in int_places__resolved on "Invalid
    unicode (byte sequence mismatch) detected in segment statistics update"
    (refresh-reference.yml 37649648453 and 37683153349, 2026-10-07). DuckDB
    checks a string's UTF-8 only as it writes a table, so no expression fails
    first and try_cast() cannot catch it: on DuckDB 1.5.4, a name with a cut
    character planted through Arrow failed CREATE TABLE AS with that same
    error, try_cast(name as varchar) failed the same way, and
    try(decode(encode(name))) gave NULL and kept "Parc Montréal" as it was
    (measured 2026-10-08, a scratch probe). decode() is what checks the bytes,
    and try() turns its error into NULL.

    Where the broken bytes come from is unknown (@unvalidated): every input of
    int_places__resolved is a table that passed the same check when written,
    run 26's second attempt built the model on the same pinned inputs, and
    neither the strings the model cuts nor python_strip() break a character on
    DuckDB 1.5.4 or 1.5.5. broken_text_report() names each broken column with
    its first 60 bytes in hex, so the next run that meets one says which column
    and which place. -#}

{% macro storable_text(column) -%}
    try(decode(encode({{ column }})))
{%- endmacro %}

{#- 'column=HEX' for each of `columns` holding text DuckDB cannot store,
    joined with '; '; null when every one is storable. -#}
{% macro broken_text_report(columns) -%}
    nullif(
        array_to_string(
            list_filter(
                [
                    {%- for column in columns %}
                    case
                        when {{ column }} is not null and {{ storable_text(column) }} is null
                            then '{{ column }}=' || left(hex(encode({{ column }})), 120)
                    end{{ "," if not loop.last }}
                    {%- endfor %}
                ],
                broken -> broken is not null
            ),
            '; '
        ),
        ''
    )
{%- endmacro %}

{#- A post-hook: logs the rows of `relation` whose broken_text is set, at most
    25, so the run's own log names them; dbt prints a warned test's row count
    and nothing of its rows. -#}
{% macro log_broken_text(relation, keys) %}
    {%- if execute %}
        {%- set found = run_query(
            "select " ~ keys | join(", ") ~ ", broken_text from " ~ relation
            ~ " where broken_text is not null order by all limit 25"
        ) %}
        {%- for row in found.rows %}
            {%- set line = row.values() | join(" | ") %}
            {%- do log("-- broken text in " ~ relation.identifier ~ ": " ~ line, info=True) %}
        {%- endfor %}
    {%- endif %}
    select 1
{% endmacro %}
