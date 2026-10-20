{#-
    A SEASON A SOURCE STATES IN WORDS (int_closures__club_notices' rule 1;
    pipeline/ELT.md, "Status, water and expiry rules", rule 4: a closure's
    expiry is "neither infinite nor last year's date"). A row's `season` is
    the source's own words for a period that recurs every year, staged from
    the field seeds/notice_source_fields.csv names (COTREX's
    Closure_Period). These two macros read it, one rule for every source.

    notice_season_part(season, part) is one part of the period it states,
    an INTEGER, or null for every part where it states none: `part` is
    'start_month', 'start_day', 'end_month' or 'end_day'.

    NARROW ON PURPOSE. The first place the text holds a month and a day,
    then "-", an en or em dash, "to", "through", "thru" or "until", then a
    month and a day, with no year after the second day: "December 1 -
    April 30", "Dec 1 - Feb 28" (make_dbt_fixtures.py's fixture row), "Area
    A: April 25 - June 20", and "December 1 - April 15. May be extended to
    April 30", read as its first range. A month is its name or its
    three-letter abbreviation, or "sept" (notice_month_number(),
    macros/notice_title_start_day.sql), so a misspelt one is no month. Read
    as no season: 'Year-round', 'Year-round closure', 'Wintering wildlife',
    a list of dated nights ('Between 4:30pm and 6am: July 21-22, 2025 …'),
    and "December 1, 2025 - April 30, 2026", a range with its years, which
    is one closure and not a season. Measured on COTREX's 128 rows read live
    2026-10-15: 108 state a range this reads; the other 20 are 16
    year-round, 2 wintering wildlife, the list of nights and 'Februrary 1 -
    August 15'.

    notice_season_day(start_month, start_day, end_month, end_day,
    build_date, which) is the period's first (`which` 'start') or last
    ('end') day in the first year whose last day is not more than one day
    behind `build_date`, notice_has_ended()'s margin: the season under way
    on the build's date, or else the next one. A period that wraps the year
    ('November 1 - March 14') ends in the year after it starts. A day its
    month does not have is the month's last (February 29 in a year without
    one is the 28th). Null where any part is null.

    Example (int_closures__club_notices):

        {{ notice_season_part('season', 'start_month') }} as season_start_month
        {{ notice_season_day('season_start_month', 'season_start_day',
            'season_end_month', 'season_end_day', 'build_date', 'end') }}
-#}
{% macro notice_season_part(season, part) -%}
    {#- Groups: 1 and 2 the first month and day, 3 and 4 the last, 5 a year
        written after the last day, which makes it no season. -#}
    {%- set period -%}
        \b([a-z]+)\.?\s+([0-9]{1,2})(?:st|nd|rd|th)?\s*(?:-|–|—|to|through|thru|until)\s*([a-z]+)\.?\s+([0-9]{1,2})(?:st|nd|rd|th)?\b(\s*,?\s*[0-9]{4})?
    {%- endset -%}
    {%- set text = "lower(coalesce(" ~ season ~ ", ''))" -%}
    {%- set groups = {'start_month': 1, 'start_day': 2, 'end_month': 3, 'end_day': 4} -%}
    {%- set start_month = notice_month_number("regexp_extract(" ~ text ~ ", '" ~ period ~ "', 1)") -%}
    {%- set end_month = notice_month_number("regexp_extract(" ~ text ~ ", '" ~ period ~ "', 3)") -%}
    {%- set start_day = "try_cast(nullif(regexp_extract(" ~ text ~ ", '" ~ period ~ "', 2), '') as integer)" -%}
    {%- set end_day = "try_cast(nullif(regexp_extract(" ~ text ~ ", '" ~ period ~ "', 4), '') as integer)" -%}
    {%- set value = {'start_month': start_month, 'start_day': start_day, 'end_month': end_month, 'end_day': end_day}[part] -%}
    case
        when
            {{ start_month }} is not null
            and {{ end_month }} is not null
            and {{ start_day }} between 1 and 31
            and {{ end_day }} between 1 and 31
            and regexp_extract({{ text }}, '{{ period }}', 5) = ''
            then {{ value }}
    end
{%- endmacro %}

{% macro notice_season_day(start_month, start_day, end_month, end_day, build_date, which) -%}
    {%- set wraps = "case when " ~ end_month ~ " * 100 + " ~ end_day ~ " < " ~ start_month ~ " * 100 + "
        ~ start_day ~ " then 1 else 0 end" -%}
    {%- set last_year = "year(" ~ build_date ~ ") - 1" -%}
    {%- set this_year = "year(" ~ build_date ~ ")" -%}
    {%- set year -%}
        case
            when
                {{ notice_season_clamped_day(last_year ~ ' + ' ~ wraps, end_month, end_day) }}
                >= {{ build_date }} - 1
                then {{ last_year }}
            when
                {{ notice_season_clamped_day(this_year ~ ' + ' ~ wraps, end_month, end_day) }}
                >= {{ build_date }} - 1
                then {{ this_year }}
            else {{ this_year }} + 1
        end
    {%- endset -%}
    case
        when
            {{ start_month }} is not null
            and {{ start_day }} is not null
            and {{ end_month }} is not null
            and {{ end_day }} is not null
            then
            {%- if which == 'start' %}
                {{ notice_season_clamped_day(year, start_month, start_day) }}
            {%- else %}
                {{ notice_season_clamped_day('(' ~ year ~ ') + ' ~ wraps, end_month, end_day) }}
            {%- endif %}
    end
{%- endmacro %}

{#- The day `day` of month `month` in `year`, or the month's last day where
    the month is shorter. -#}
{% macro notice_season_clamped_day(year, month, day) -%}
    make_date(
        {{ year }},
        {{ month }},
        least(
            {{ day }},
            day(last_day(make_date({{ year }}, {{ month }}, 1)))
        )
    )
{%- endmacro %}
