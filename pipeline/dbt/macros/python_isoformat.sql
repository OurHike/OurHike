{#-
    Python's datetime.fromisoformat() and date.fromisoformat(), as
    lib/atc_updates.py reads ATC's dateModified and a reviewed file's
    reviewed_at, for the gate that moved to SQL (#1793, stage 3, CL07).
-#}

{#- datetime.fromisoformat(text) as a TIMESTAMPTZ: the instant, for a stamp
    with an offset; for one without, its wall time read as UTC, which is what
    _modified_after() (a naive stamp's own date) and _as_utc_stamp()
    (`replace(tzinfo=timezone.utc)`) both do with it. Null where Python raises
    ValueError, and also where this cannot tell that Python would not.

    READ: YYYY-MM-DD, optionally followed by T or a space and HH:MM, then :SS
    and up to six fractional digits, then Z or an offset of +HH, +HHMM or
    +HH:MM, with optional seconds. Measured 2026-10-02 on DuckDB 1.5.5 against
    Python 3.13: each of these, 13 forms, read to the instant Python reads,
    with the session in UTC; the offset is read from the text, so the
    session's time zone does not enter. All 86 live ATC pages read that day
    carried YYYY-MM-DDTHH:MM:SS-04:00.

    NOT READ, where Python 3.11 and later do read them: the basic forms
    (20260819T162250Z), an hour with no minutes, a comma before the fraction,
    more than six fractional digits, and ISO week dates. Each is null here, so
    a page dated that way is refused, never published: the direction a gate
    on a safety path may err in. DuckDB alone would read some text Python
    refuses (`2026-8-19`), which is why the pattern comes first. -#}
{% macro python_fromisoformat_utc(text) -%}
    case
        when
            not regexp_matches(
                {{ text }},
                '^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?(Z|[+-]\d{2}(:?\d{2}(:?\d{2})?)?)?)?$'
            )
            then null
        when
            regexp_matches(
                {{ text }},
                '[T ]\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?(Z|[+-]\d{2}(:?\d{2}(:?\d{2})?)?)$'
            )
            then try_cast({{ text }} as timestamptz)
        else timezone('UTC', try_cast({{ text }} as timestamp))
    end
{%- endmacro %}

{#- date.fromisoformat(text) as a DATE, for the two forms a reviewer could
    write: YYYY-MM-DD and YYYYMMDD. Null for anything else, including the ISO
    week dates Python 3.11 and later read, so a review dated that way
    publishes no automatic row. -#}
{% macro python_date_fromisoformat(text) -%}
    case
        when regexp_matches({{ text }}, '^\d{4}-\d{2}-\d{2}$')
            then try_cast({{ text }} as date)
        when regexp_matches({{ text }}, '^\d{8}$')
            then cast(try_strptime({{ text }}, '%Y%m%d') as date)
    end
{%- endmacro %}
