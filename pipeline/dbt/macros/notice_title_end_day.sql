{#-
    THE DAY A TITLE SAYS ITS NOTICE ENDS, as a DATE, or null where the title
    states none this reads (the maintainer's poll of 2026-10-15: "a title
    that states its own end is read as the row's end").
    int_closures__club_notices takes the later of this and the row's own end
    date as its `ends_on`, and int_closures__oprhp_areas reads its areas'
    reasons by it, so a title is read the same way for every source.

    WHAT IT READS, case aside, each a whole word:
    - 'until', 'till', 'thru' or 'through', then a day: a month's name, full
      or cut short, with a day or without one, and a four-digit year ('until
      June 30, 2027', 'through June 2027', 'Until Sept. 2027'); or
      month/day/year with a year of four digits or two ('until 7/1/2025');
      or a year alone, after one of 'early', 'mid', 'late', 'spring',
      'summer', 'fall', 'autumn' or 'winter' or after nothing ('Closed Until
      2027', 'through Fall 2025');
    - a season's range of two years, the second not before the first, and
      only where it reads as a season: alone in brackets ('(2026-2027)',
      Wisconsin DNR's), after a lead word above or 'season' ('through
      2026-27'), or followed by 'season' ('2026-27 season'). Any other
      range is no end: an order number ('Closure Order No. 2023-31',
      'Forest Order #2024-28') or a past season named in passing ('2020-21
      Fire Scar Closure') reads as nothing.

    TOWARD CAUTION: a month alone is its last day, and a year alone, or a
    season of it, its December 31: a closure is read as standing to the end
    of the period its title names, never greyed inside it (Reasoned). A
    title that names several ends ('Sept. 8, 2026
    through June 2027' names one) is read at the latest.

    WHAT IT DOES NOT READ: a day with no year ('December 15 thru June 15',
    'through October 31'), which names no year a reader could check; 'to'
    ('due to 2026 storms' would read as an end); 'until further notice'; a
    time of day. A day that does not exist ('until June 31, 2027') is null.

    Measured on UA's notices.json of 2026-10-15 21:26 UTC: 29 of its 9,298
    titles hold 'until', 'till', 'thru' or 'through' before a word, or a
    range of years; this reads an end in 18 of them (15 distinct titles), and
    the end moves on 10 (the rest already carried it). The reviewer's
    prototype of 2026-10-15 read 75 titles on a wider pattern and found no
    false positive; this one is narrower, @unvalidated beyond those 29.
-#}
{% macro notice_title_end_day(title) -%}
    {%- set lead -%}
        (?i)(?:^|[^a-z])(?:until|till|thru|through)\s+
    {%- endset -%}
    {%- set month_day -%}
        {{ lead }}([a-z]{3,9})\.?(?:\s+([0-9]{1,2})(?:st|nd|rd|th)?)?,?\s+([0-9]{4})(?:[^0-9]|$)
    {%- endset -%}
    {%- set numeric -%}
        {{ lead }}([0-9]{1,2})/([0-9]{1,2})/([0-9]{4}|[0-9]{2})(?:[^0-9/]|$)
    {%- endset -%}
    {%- set year_alone -%}
        {{ lead }}(?:(?:early|mid|late|spring|summer|fall|autumn|winter)\s+)?([0-9]{4})(?:[^0-9/-]|-[^0-9]|-$|$)
    {%- endset -%}
    {%- set years -%}
        ((?:19|20)[0-9]{2})\s*[-–—]\s*((?:19|20)?[0-9]{2})
    {%- endset -%}
    {%- set bracketed_range -%}
        \(\s*{{ years }}\s*\)
    {%- endset -%}
    {%- set lead_range -%}
        (?i)(?:^|[^a-z])(?:until|till|thru|through|season)\s+{{ years }}(?:[^0-9/-]|$)
    {%- endset -%}
    {%- set season_range -%}
        (?i)(?:^|[^0-9/#.-])\s*{{ years }}\s+season(?:[^a-z]|$)
    {%- endset -%}
    {%- set months -%}
        ['january', 'february', 'march', 'april', 'may', 'june', 'july',
        'august', 'september', 'october', 'november', 'december']
    {%- endset -%}
    {%- set text = "coalesce(" ~ title ~ ", '')" -%}
    greatest(
        list_max(
            list_transform(
                regexp_extract_all({{ text }}, '{{ month_day }}'),
                lambda found: {{ notice_title_end_month_day('found', month_day, months) }}
            )
        ),
        list_max(
            list_transform(
                regexp_extract_all({{ text }}, '{{ numeric }}'),
                lambda found: try_cast(
                    printf(
                        '%04d-%02d-%02d',
                        case
                            when length(regexp_extract(found, '{{ numeric }}', 3)) = 4
                                then cast(regexp_extract(found, '{{ numeric }}', 3) as integer)
                            when cast(regexp_extract(found, '{{ numeric }}', 3) as integer) < 69
                                then 2000 + cast(regexp_extract(found, '{{ numeric }}', 3) as integer)
                            else 1900 + cast(regexp_extract(found, '{{ numeric }}', 3) as integer)
                        end,
                        cast(regexp_extract(found, '{{ numeric }}', 1) as integer),
                        cast(regexp_extract(found, '{{ numeric }}', 2) as integer)
                    ) as date
                )
            )
        ),
        list_max(
            list_transform(
                regexp_extract_all({{ text }}, '{{ year_alone }}'),
                lambda found: make_date(
                    cast(regexp_extract(found, '{{ year_alone }}', 1) as integer), 12, 31
                )
            )
        ),
        list_max(
            list_transform(
                regexp_extract_all({{ text }}, '{{ bracketed_range }}'),
                lambda found: {{ notice_title_end_year_range('found', bracketed_range) }}
            )
        ),
        list_max(
            list_transform(
                regexp_extract_all({{ text }}, '{{ lead_range }}'),
                lambda found: {{ notice_title_end_year_range('found', lead_range) }}
            )
        ),
        list_max(
            list_transform(
                regexp_extract_all({{ text }}, '{{ season_range }}'),
                lambda found: {{ notice_title_end_year_range('found', season_range) }}
            )
        )
    )
{%- endmacro %}

{#- One 'until <month> [day,] <year>' match as its day: the day where one is
    named, else the month's last; null where the word is no month's name. -#}
{% macro notice_title_end_month_day(found, pattern, months) -%}
    case
        when
            list_position(
                list_transform(
                    {{ months }},
                    lambda month: starts_with(
                        month, lower(regexp_extract({{ found }}, '{{ pattern }}', 1))
                    )
                ),
                true
            ) is null
            then null
        when regexp_extract({{ found }}, '{{ pattern }}', 2) = ''
            then last_day(
                make_date(
                    cast(regexp_extract({{ found }}, '{{ pattern }}', 3) as integer),
                    list_position(
                        list_transform(
                            {{ months }},
                            lambda month: starts_with(
                                month,
                                lower(regexp_extract({{ found }}, '{{ pattern }}', 1))
                            )
                        ),
                        true
                    ),
                    1
                )
            )
        else cast(
            try_strptime(
                regexp_extract({{ found }}, '{{ pattern }}', 3)
                || '-'
                || list_position(
                    list_transform(
                        {{ months }},
                        lambda month: starts_with(
                            month,
                            lower(regexp_extract({{ found }}, '{{ pattern }}', 1))
                        )
                    ),
                    true
                )
                || '-'
                || regexp_extract({{ found }}, '{{ pattern }}', 2),
                '%Y-%m-%d'
            ) as date
        )
    end
{%- endmacro %}

{#- One range of years as December 31 of its second, which a two-digit year
    takes the first's century for; null where the second is before the
    first. -#}
{% macro notice_title_end_year_range(found, pattern) -%}
    {%- set first = "cast(regexp_extract(" ~ found ~ ", '" ~ pattern ~ "', 1) as integer)" -%}
    {%- set second_text = "regexp_extract(" ~ found ~ ", '" ~ pattern ~ "', 2)" -%}
    {%- set second -%}
        cast(
            case
                when length({{ second_text }}) = 2
                    then substr(regexp_extract({{ found }}, '{{ pattern }}', 1), 1, 2) || {{ second_text }}
                else {{ second_text }}
            end as integer
        )
    {%- endset -%}
    case
        when {{ second }} >= {{ first }} then make_date({{ second }}, 12, 31)
    end
{%- endmacro %}
