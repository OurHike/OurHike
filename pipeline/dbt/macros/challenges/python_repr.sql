{#-
    Python's repr() and str() of a value json.loads gave, so a refusal message
    ported from Python prints a value the way today's prints it with `!r` or
    in an f-string. Written for the challenges family (lib/challenges.py,
    export_challenges.py), and usable by any port whose messages do the same.
    Each expands to a few kilobytes of SQL, so a model computes each value's
    repr once, in a CTE, rather than calling these at every message.

    A STRING is quoted as Python quotes one: single quotes, unless the string
    holds a single quote and no double one. Backslash and the chosen quote are
    escaped, and tab, newline and carriage return are written \t, \n and \r,
    as Python writes them. Python also writes any other character
    str.isprintable() refuses as \xhh, \uhhhh or \Uhhhhhhhh (a NUL, a
    zero-width space, a no-break space); here those print raw. Only a
    message reads these, never a published field, and an exact escape needed
    a lambda over every character that SQLFluff took over 20 s to parse per
    model (measured 2026-10-02, sqlfluff 4.3.0), so the cheap half is done
    exactly and the rest is this stated difference.

    A DOUBLE prints as cast(x as varchar): measured 2026-10-02 on DuckDB
    1.5.5, it equalled Python's repr(float) on all 40,020 doubles tried
    (20,000 uniform in -3000 to 3000, 20,000 log-uniform in 1e-12 to 1e20,
    and 1e16, 1e-05, -0.0, 5e-324 and the largest double among 20 more). On
    dbt 2.0.6's bundled 1.5.4 it is @unvalidated beyond the unit tests'
    values; a probe over the same doubles through `dbt show` would settle it.

    A LIST prints as Python prints one, `['atc']`, with each element's repr;
    a list or object inside it prints as its JSON text. AN OBJECT prints as
    its JSON text, `{"a":1}` where Python prints `{'a': 1}`. No reviewed file
    puts an object, or a list inside a list, where a message quotes it, and
    no unit test does.
-#}

{#- repr() of a VARCHAR expression. -#}
{%- macro python_str_repr(text) -%}
    {%- set quote -%}
        case when contains({{ text }}, chr(39)) and not contains({{ text }}, chr(34)) then chr(34) else chr(39) end
    {%- endset -%}
    (
        {{ quote }}
        || replace(replace(replace(replace(replace(
            {{ text }},
            chr(92), chr(92) || chr(92)),
            {{ quote }}, chr(92) || {{ quote }}),
            chr(9), chr(92) || 't'),
            chr(10), chr(92) || 'n'),
            chr(13), chr(92) || 'r')
        || {{ quote }}
    )
{%- endmacro -%}

{#- repr() of a JSON value that is not a string: None, True and False, a number, or JSON text. -#}
{%- macro python_plain_repr(value) -%}
    case coalesce(json_type({{ value }}), 'NULL')
        when 'NULL' then 'None'
        when 'BOOLEAN'
            then case when json_extract_string({{ value }}, '$') = 'true' then 'True' else 'False' end
        when 'DOUBLE' then cast(cast({{ value }} as double) as varchar)
        when 'BIGINT' then cast(cast({{ value }} as hugeint) as varchar)
        when 'UBIGINT' then cast(cast({{ value }} as hugeint) as varchar)
        else cast({{ value }} as varchar)
    end
{%- endmacro -%}

{#-
    repr() of a JSON value: None for SQL NULL (absent) and JSON null alike, as
    dict.get() gives None for both. A value that is not a list is read as a
    list of itself, so each element's repr is written once and the brackets
    are the only difference: half the SQL of a separate branch for a list,
    which is what SQLFluff spends its time parsing.
-#}
{%- macro python_repr(value) -%}
    (
        case when json_type({{ value }}) = 'ARRAY' then '[' else '' end
        || array_to_string(list_transform(
            case
                when json_type({{ value }}) = 'ARRAY' then cast({{ value }} as json[])
                else [cast({{ value }} as json)]
            end,
            lambda element: case
                when json_type(element) = 'VARCHAR'
                    then {{ python_str_repr("json_extract_string(element, '$')") }}
                else {{ python_plain_repr('element') }}
            end
        ), ', ')
        || case when json_type({{ value }}) = 'ARRAY' then ']' else '' end
    )
{%- endmacro -%}

{#- str() of a JSON value, given its repr: a string as itself, anything else as its repr. -#}
{%- macro python_str(value, repr) -%}
    case
        when json_type({{ value }}) = 'VARCHAR' then json_extract_string({{ value }}, '$')
        else {{ repr }}
    end
{%- endmacro -%}
