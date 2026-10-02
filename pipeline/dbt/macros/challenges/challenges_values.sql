{#-
    lib/challenges.py's four value helpers, over a JSON value as json.loads
    gave it to them, for the int_challenges__ models. Each is held to its
    Python by the unit tests tests/test_dbt_challenges_parity.py runs the
    Python over.
-#}

{#- _text(): the string with str.strip() applied, or '' for anything that is not a string. -#}
{%- macro challenges_text(value) -%}
    case
        when json_type({{ value }}) = 'VARCHAR'
            then {{ python_strip("json_extract_string(" ~ value ~ ", '$')") }}
        else ''
    end
{%- endmacro -%}

{#-
    _id_ok(): a string of lowercase words joined by hyphens, at most
    ID_MAX_CHARS long. Stricter than the Python on purpose in one place:
    re.match's `$` also matches before a trailing newline, so "summer-list\n"
    passes _id_ok() and would publish, newline and all, as an id every tag of
    it is keyed by. Here the whole string must match.
-#}
{%- macro challenges_id_ok(value) -%}
    coalesce(
        json_type({{ value }}) = 'VARCHAR'
        and length(json_extract_string({{ value }}, '$')) <= {{ var('challenges_id_max_chars') }}
        and regexp_full_match(json_extract_string({{ value }}, '$'), '{{ var("challenges_id_pattern") }}'),
        false
    )
{%- endmacro -%}

{#-
    _date(): a YYYY-MM-DD string naming a real day. The Python matches
    `^\d{4}-\d{2}-\d{2}$` and then needs date.fromisoformat() to accept it,
    which refuses a trailing newline, a non-ASCII digit and year 0 (measured
    2026-10-02 on Python 3.12 and 3.13), so ASCII digits, a real calendar
    day and a year from 1 are the whole rule. DuckDB's strptime reads year
    0000 as 1 BC, hence the guard.
-#}
{%- macro challenges_date_ok(value) -%}
    coalesce(
        json_type({{ value }}) = 'VARCHAR'
        and regexp_full_match(json_extract_string({{ value }}, '$'), '[0-9]{4}-[0-9]{2}-[0-9]{2}')
        and not starts_with(json_extract_string({{ value }}, '$'), '0000')
        and try_strptime(json_extract_string({{ value }}, '$'), '%Y-%m-%d') is not null,
        false
    )
{%- endmacro -%}

{#-
    _https_or_none()'s first half: the stripped https URL, or null for a
    value that is blank, not a string, or refused. A photo the phone loads is
    an https URL or nothing.
-#}
{%- macro challenges_https(value) -%}
    case
        when starts_with({{ challenges_text(value) }}, 'https://')
            then {{ challenges_text(value) }}
    end
{%- endmacro -%}

{#- _https_or_none()'s second half: blank (or not a string) is acceptable, as is an https URL; anything else is refused. -#}
{%- macro challenges_https_ok(value) -%}
    (
        {{ challenges_text(value) }} = ''
        or starts_with({{ challenges_text(value) }}, 'https://')
    )
{%- endmacro -%}
