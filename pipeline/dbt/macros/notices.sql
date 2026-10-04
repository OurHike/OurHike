{#-
    The club notice sources' shared pieces (decision 53, phase C): what every
    generated base and staging model calls (pipeline/generate_notice_models.py
    writes them), and int_closures__club_notices reads.
-#}

{#- A raw table, or an empty one of the same key columns where the raw table
    does not exist in this warehouse.

    A conditions leg withdraws a table whose reader could not be read
    (extract/_warehouse.py's committed_tables(), an `unavailable` outcome),
    takes on at most ten tables it has never loaded per run
    (extract/_run.py's NEW_TABLES_PER_LEG_RUN), and leaves out a table whose
    read failed before its hints. Each of those is a missing table, and a
    model that selects from a missing table fails the build, which skips
    every model downstream of it: every club's closures, ATC's and NYNJTC's
    included. So a generated base model reads its raw table through this,
    and a missing table reads as no rows. The gate then holds that source
    back for having no rows that a count of zero proves
    (int_closures__gate), so absent still means unknown, never "nothing
    closed".

    `columns` are the raw columns the model itself names (a base model's key
    and geometry), each typed varchar in the empty table unless written
    `name:type`; `_loaded_at` and `_dlt_id` are added. dbt's load_relation()
    answers at run time (measured
    on dbt 2.0.6, 2026-10-03, a scratch project: a missing source built an
    empty view and a present one read its rows). Under SQLFluff's jinja
    templater, where load_relation is not defined, the macro renders the
    relation, so the lint reads the real query. -#}
{% macro notice_raw_table(relation, columns) -%}
    {%- if execute is defined and execute and load_relation is defined and load_relation(relation) is none -%}
        (
            select
                {% for column in columns -%}
                {%- set parts = column.split(':') -%}
                cast(null as {{ parts[1] if parts | length > 1 else 'varchar' }}) as "{{ parts[0] }}",
                {% endfor -%}
                cast(null as timestamptz) as _loaded_at,
                cast(null as varchar) as _dlt_id
            where false
        )
    {%- else -%}
        {{ relation }}
    {%- endif -%}
{%- endmacro %}

{#- A source field's text, by its raw column's name, out of a staging model's
    `fields.row_json` (the base row as JSON): null where the column is absent,
    null or blank, so a field the source drops or renames reads as unknown
    rather than failing the build. `path` reads a value inside a JSON column
    (a WordPress title's `$.rendered`); `as_list` joins a JSON list of text
    with ', ' (a feed item's categories). -#}
{% macro notice_field(column, path=none, as_list=false) -%}
    {%- set value = "json_extract_string(fields.row_json, '$.\"" ~ column ~ "\"')" -%}
    {%- if path is not none -%}
        {%- set value = "json_extract_string(" ~ value ~ ", '" ~ path ~ "')" -%}
    {%- endif -%}
    {%- if as_list -%}
        {%- set value = "array_to_string(try_cast(json(" ~ value ~ ") as varchar[]), ', ')" -%}
    {%- endif -%}
    nullif(trim({{ value }}), '')
{%- endmacro %}

{#- A source's date or time, as the source states it, as TIMESTAMPTZ, or
    null where it is none of these. Read in this order, the first that
    parses:
    - epoch milliseconds, eleven digits or more: ArcGIS's
      esriFieldTypeDate, which extract/_kinds.py's ESRI_TYPES lands as bigint;
    - anything DuckDB casts to a timestamp with time zone: ISO 8601 with or
      without an offset (Atom, WordPress's modified_gmt, ArcGIS's DateOnly
      'YYYY-MM-DD', NPS's '2026-10-02 00:00:00.0'). Without an offset the
      session's zone applies, which build_marts.py sets to UTC;
    - RFC 822, an RSS pubDate, with 'GMT' read as '+0000';
    - month/day/year, the Ouachita condition report's.
    Never filled in: a date the source states in words ('Until further
    notice') is null here, and stays in the source's own fields. -#}
{% macro notice_instant(text) -%}
    coalesce(
        case
            when regexp_full_match({{ text }}, '-?[0-9]{11,}')
                then to_timestamp(cast({{ text }} as bigint) / 1000.0)
        end,
        try_cast({{ text }} as timestamptz),
        try_strptime(
            replace({{ text }}, ' GMT', ' +0000'), '%a, %d %b %Y %H:%M:%S %z'
        ),
        cast(try_strptime({{ text }}, '%m/%d/%Y') as timestamptz)
    )
{%- endmacro %}

{#- A source's text as words: a WordPress-shaped JSON value's `rendered`
    member where it is one (a post's `content` lands as that JSON), HTML tags
    cut out, and runs of whitespace made one space, so that a paragraph is
    compared as a reader would see it. -#}
{% macro notice_wording_text(text) -%}
    trim(
        regexp_replace(
            regexp_replace(
                coalesce(
                    json_extract_string(try_cast({{ text }} as json), '$.rendered'),
                    {{ text }}
                ),
                '<[^>]*>', ' ', 'g'
            ),
            '\s+', ' ', 'g'
        )
    )
{%- endmacro %}

{#- Whether a text value is a source's own wording rather than a short fact:
    at least `min_chars` characters with a space in it.
    int_warnings__notice_wording_unioned keeps only such values, so that a
    short value a mart may carry for its own reasons ('Closed', 'Yes', a
    road name) is never read as a source's paragraph, and the leak check
    cannot fail a build on a coincidence. @unvalidated: 30 is a guess at the
    shortest sentence-like wording, not a measurement; a leak shorter than it
    goes unseen. What would settle it is the length of the shortest
    description, note or comment value across the live notice layers. -#}
{% macro notice_is_wording(text, min_chars=30) -%}
    (
        length({{ text }}) >= {{ min_chars }}
        and contains({{ text }}, ' ')
    )
{%- endmacro %}

{#- One hash of a raw row's content, exactly as duplicates_are_exact compares
    two rows on a key: macros/row_hash.sql's row_hash() over every column of
    the raw table but the server's own row ids (row_hash_row_ids()). A club
    notice source's base model counts the different hashes on each key
    (`key_versions`), and int_closures__gate holds a source with any key over
    one, so a conflict holds that source's notices rather than publishing one
    copy chosen by load order. The column list is read from the warehouse,
    so a table that does not exist yet hashes as one row(null): no conflict,
    and no rows to have one. -#}
{% macro notice_row_version(relation) -%}
    {{ row_hash(relation, row_hash_row_ids()) }}
{%- endmacro %}
