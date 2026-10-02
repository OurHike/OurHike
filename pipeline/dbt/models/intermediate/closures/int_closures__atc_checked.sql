-- Every row of reference/atc_updates.json, read field by field and checked
-- against lib/atc_updates.py's file_problems() (CL01-CL06), with EVERY
-- problem a row has, in the order row_problems() finds them, in `problems`.
-- An empty list means the row is fine. int_closures__gate fails ATC's whole
-- file on any problem, as export_atc_updates.py refuses it (CL05): "a
-- partial set of safety notices is worse than none". The review is the
-- file's, and the gate reads it from base_atc__atc_updates.
--
-- THE CHECKS, IN row_problems()'S ORDER, each only for a field the row has
-- (`field in row`; a null value is present):
--   every field present (REQUIRED_FIELDS)       CL06
--   atc_id, title: a string with something besides whitespace
--   category: one ATC publishes                 CL02, var atc_update_categories
--   states: a non-empty list of non-blank strings
--   each mile: a number, not a boolean, inside 0.5-2197.5     CL01
--   end before start: refused, never swapped    CL03
--   obstructs_trail: a real boolean             CL03
--   updated_at: a string with something in it
--   source_url: an http or https URL            CL03
-- and then, across the file, an atc_id a row before it already used (CL04).
-- A row that is not an object gets "update N is not an object" and nothing
-- else, as file_problems() skips it.
--
-- A FIELD IS ITS JSON (base_atc__atc_trail_updates lands each row as written),
-- so "476.6" is not a mile and "true" is not a boolean, as in the Python.
-- Each problem carries the row's label, its atc_id or "update N", and
-- renders a value as JSON where row_problems() uses Python's repr.
--
-- WHERE THIS IS STRICTER, deliberately, each a row file_problems() passes and
-- this refuses (tests/test_dbt_conditions_parity.py lists them): a
-- source_url's scheme is read as written, where urlparse() first strips
-- leading spaces and control characters, and the phone would then open the
-- link with them still in it, as int_podcasts__checked reads a link.
with updates as (
    select * from {{ ref('base_atc__atc_trail_updates') }}
),

fields as (
    select
        atc_update_row_key,
        file_row,
        _loaded_at,
        json_type(atc_update) as update_type,
        case
            when json_type(atc_update) = 'OBJECT' then json_keys(atc_update)
            else []
        end as present,
        json_extract(atc_update, '$.atc_id') as atc_id_json,
        json_extract(atc_update, '$.title') as title_json,
        json_extract(atc_update, '$.category') as category_json,
        json_extract(atc_update, '$.states') as states_json,
        json_extract(atc_update, '$.start_mile_marker') as start_json,
        json_extract(atc_update, '$.end_mile_marker') as end_json,
        json_extract(atc_update, '$.obstructs_trail') as obstructs_json,
        json_extract(atc_update, '$.updated_at') as updated_json,
        json_extract(atc_update, '$.source_url') as source_url_json
    from updates
),

typed as (
    select
        *,
        coalesce(json_type(atc_id_json), 'NULL') as atc_id_type,
        coalesce(json_type(title_json), 'NULL') as title_type,
        coalesce(json_type(category_json), 'NULL') as category_type,
        coalesce(json_type(states_json), 'NULL') as states_type,
        coalesce(json_type(start_json), 'NULL') as start_type,
        coalesce(json_type(end_json), 'NULL') as end_type,
        coalesce(json_type(obstructs_json), 'NULL') as obstructs_type,
        coalesce(json_type(updated_json), 'NULL') as updated_type,
        coalesce(json_type(source_url_json), 'NULL') as source_url_type,
        case
            when json_type(states_json) = 'ARRAY'
                then cast(states_json as json[])
        end as state_items
    from fields
),

-- Each field as a value, where its JSON type allows one.
parsed as (
    select
        *,
        case
            when atc_id_type = 'VARCHAR'
                then json_extract_string(atc_id_json, '$')
        end as atc_id,
        case
            when title_type = 'VARCHAR'
                then json_extract_string(title_json, '$')
        end as title,
        case
            when category_type = 'VARCHAR'
                then json_extract_string(category_json, '$')
        end as category,
        case
            when start_type in ('UBIGINT', 'BIGINT', 'DOUBLE')
                then cast(json_extract_string(start_json, '$') as double)
        end as start_mile_marker,
        case
            when end_type in ('UBIGINT', 'BIGINT', 'DOUBLE')
                then cast(json_extract_string(end_json, '$') as double)
        end as end_mile_marker,
        case
            when obstructs_type = 'BOOLEAN'
                then cast(json_extract_string(obstructs_json, '$') as boolean)
        end as obstructs_trail,
        case
            when updated_type = 'VARCHAR'
                then json_extract_string(updated_json, '$')
        end as updated_at,
        case
            when source_url_type = 'VARCHAR'
                then json_extract_string(source_url_json, '$')
        end as source_url,
        -- lib/atc_updates.py's label for a row in a message: its atc_id when
        -- that is truthy in Python's sense, else "update N".
        case
            when
                atc_id_type = 'VARCHAR'
                and json_extract_string(atc_id_json, '$') != ''
                then json_extract_string(atc_id_json, '$')
            when
                atc_id_type = 'BOOLEAN'
                and cast(atc_id_json as varchar) = 'true'
                then 'True'
            when
                atc_id_type in ('UBIGINT', 'BIGINT', 'DOUBLE')
                and cast(json_extract_string(atc_id_json, '$') as double) != 0
                then cast(atc_id_json as varchar)
            when
                atc_id_type in ('ARRAY', 'OBJECT')
                and cast(atc_id_json as varchar) not in ('[]', '{}')
                then cast(atc_id_json as varchar)
            else 'update ' || file_row
        end as row_label
    from typed
),

-- One check per column, null where the row passes it, in row_problems()'s
-- order. A field the row does not have is checked only by `missing`.
checks as (
    select
        *,
        list_transform(
            list_filter(
                [
                    'atc_id', 'title', 'category', 'states',
                    'start_mile_marker', 'end_mile_marker', 'obstructs_trail',
                    'updated_at', 'source_url'
                ],
                lambda f: not list_contains(present, f)
            ),
            lambda f: 'missing ' || f
        ) as missing,
        case
            when
                list_contains(present, 'atc_id')
                and not coalesce(
                    {{ python_strip('atc_id') }} != '', false
                )
                then 'atc_id is empty'
        end as empty_atc_id,
        case
            when
                list_contains(present, 'title')
                and not coalesce({{ python_strip('title') }} != '', false)
                then 'title is empty'
        end as empty_title,
        case
            when
                list_contains(present, 'category')
                and not coalesce(
                    list_contains({{ var('atc_update_categories') }}, category),
                    false
                )
                then
                    'category ' || cast(category_json as varchar)
                    || ' is not one ATC publishes ('
                    || array_to_string(
                        list_sort({{ var('atc_update_categories') }}), ', '
                    )
                    || ')'
        end as bad_category,
        case
            when
                list_contains(present, 'states')
                and not coalesce(
                    len(state_items) > 0
                    and list_bool_and(list_transform(
                        state_items,
                        lambda s: json_type(s) = 'VARCHAR'
                        and {{ python_strip(
                            "json_extract_string(s, '$')"
                        ) }} != ''
                    )),
                    false
                )
                then 'states must be a non-empty list of state codes'
        end as bad_states,
        {%- for field, side in [
            ('start_mile_marker', 'start'),
            ('end_mile_marker', 'end'),
        ] %}
        case
            when not list_contains(present, '{{ field }}') then null
            when {{ side }}_type not in ('UBIGINT', 'BIGINT', 'DOUBLE')
                then
                    '{{ field }} is '
                    || coalesce(cast({{ side }}_json as varchar), 'null')
                    || ', which is not a mile'
            when
                not {{ field }} between {{ var('atc_trail_mile_min') }}
                and {{ var('atc_trail_mile_max') }}
                then
                    '{{ field }} is ' || cast({{ side }}_json as varchar)
                    || ', outside the trail''s own extent ('
                    || '{{ var("atc_trail_mile_min") }}-'
                    || '{{ var("atc_trail_mile_max") }}). '
                    || 'A mile off the end of the trail is a mistake with a '
                    || 'decimal point in it, not a place - see '
                    || 'lib/atc_updates.py.'
        end as bad_{{ side }}_mile,
        {%- endfor %}
        -- Not silently swapped: the range the reviewer meant is not
        -- recoverable from the one they wrote. As in the Python, the end may be
        -- a boolean here (a bool is an int there), and the start may not.
        case
            when
                start_type in ('UBIGINT', 'BIGINT', 'DOUBLE')
                and end_type in ('UBIGINT', 'BIGINT', 'DOUBLE', 'BOOLEAN')
                and case
                    when end_type = 'BOOLEAN'
                        then cast(
                            cast(json_extract_string(end_json, '$') as boolean)
                            as double
                        )
                    else end_mile_marker
                end < start_mile_marker
                then
                    'end_mile_marker '
                    || case
                        when
                            end_type = 'BOOLEAN'
                            and cast(end_json as varchar) = 'true'
                            then 'True'
                        when end_type = 'BOOLEAN' then 'False'
                        else cast(end_json as varchar)
                    end
                    || ' is before start_mile_marker '
                    || cast(start_json as varchar)
        end as reversed_range,
        case
            when
                list_contains(present, 'obstructs_trail')
                and obstructs_type != 'BOOLEAN'
                then
                    'obstructs_trail must be true or false - whether a hiker '
                    || 'is stopped from walking through, which is not the same '
                    || 'question as ATC''s category (a closed shelter is a '
                    || '`Closure` and leaves the trail open)'
        end as bad_obstructs,
        case
            when
                list_contains(present, 'updated_at')
                and not coalesce({{ python_strip('updated_at') }} != '', false)
                then
                    'updated_at is empty - it is ATC''s own date and the one '
                    || 'a hiker cares about'
        end as empty_updated_at,
        case
            when
                list_contains(present, 'source_url')
                and not coalesce(
                    lower(regexp_extract(
                        source_url, '^([A-Za-z][A-Za-z0-9+.-]*):', 1
                    )) in ('http', 'https'),
                    false
                )
                then
                    'source_url '
                    || coalesce(cast(source_url_json as varchar), 'null')
                    || ' is not an http(s) URL'
        end as bad_source_url
    from parsed
),

-- CL04: an atc_id an earlier row already used. file_problems() remembers
-- every string id it meets, whatever else is wrong with its row.
repeats as (
    select
        *,
        case
            when
                atc_id is not null
                and row_number() over (
                    partition by atc_id order by file_row
                ) > 1
                then atc_id || ': appears more than once'
        end as repeated
    from checks
),

listed as (
    select
        *,
        case
            when update_type != 'OBJECT'
                then ['update ' || file_row || ' is not an object']
            else list_concat(
                list_transform(
                    list_filter(
                        list_concat(
                            missing,
                            [
                                empty_atc_id,
                                empty_title,
                                bad_category,
                                bad_states,
                                bad_start_mile, bad_end_mile, reversed_range,
                                bad_obstructs, empty_updated_at, bad_source_url
                            ]
                        ),
                        lambda p: p is not null
                    ),
                    lambda p: row_label || ': ' || p
                ),
                list_filter([repeated], lambda p: p is not null)
            )
        end as problems
    from repeats
)

select
    atc_update_row_key,
    file_row,
    row_label,
    atc_id,
    title,
    category,
    case when states_type = 'ARRAY' then states_json end as states,
    -- The miles as the reviewer wrote them, text, where each is a number: a
    -- DOUBLE in a unit-tested model's output is compared only to one decimal
    -- on dbt 2.0.6 (476.6 equals 476.64, measured by stage 3's trail_lines
    -- worker), so the exact value travels as text and int_closures__unioned
    -- casts it once.
    case
        when start_type in ('UBIGINT', 'BIGINT', 'DOUBLE')
            then cast(start_json as varchar)
    end as start_mile_text,
    case
        when end_type in ('UBIGINT', 'BIGINT', 'DOUBLE')
            then cast(end_json as varchar)
    end as end_mile_text,
    obstructs_trail,
    updated_at,
    source_url,
    problems,
    -- The same problems as one line each joined by " | ", for `dbt show` and
    -- the unit test. Null where the row is fine.
    nullif(array_to_string(problems, ' | '), '') as problem,
    -- The row as lib/atc_updates.py's published_rows() publishes it, for
    -- pub_conditions_atc_updates: each field's JSON exactly as the reviewer
    -- wrote it, so a mile written 167 stays 167 rather than becoming 167.0,
    -- and then the two constants. Only a file int_closures__gate passes is
    -- written, so every field here has passed its check.
    json_object(
        'atc_id', atc_id_json,
        'title', title_json,
        'category', category_json,
        'states', states_json,
        'start_mile_marker', start_json,
        'end_mile_marker', end_json,
        'obstructs_trail', obstructs_json,
        'updated_at', updated_json,
        'source_url', source_url_json,
        'source_key', 'atc_trail_updates',
        'review_state', 'reviewed'
    ) as published_row,
    _loaded_at
from listed
