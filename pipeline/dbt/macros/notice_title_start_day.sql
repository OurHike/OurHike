{#-
    THE DAY A TITLE SAYS A CLOSURE STARTS (int_closures__club_notices' rule
    2, c2): the date after the title's own `states_a_start` word
    (seeds/notice_words.csv: beginning, starting, starts), as a DATE, or
    null where the title states no day this reads. The model finds the word
    in the vocabulary and passes it in, so no word is named here.

    NARROW ON PURPOSE, and one rule for every source. After the word, and
    an optional "on", one of:

      "9/1", "10/15", "12/5/23", "3/1/2027"       month/day, and a year
      "Oct. 28, 2026", "June 24", "May 20th"      a month, a day, and a year

    each year optional. A month is its name or its three-letter
    abbreviation, or "sept". Nothing else is a day: "Beginning Fall 2027",
    "starting late-September", "beginning September 2025" and "starts this
    weekend" read as none, so the start word keeps qualifying the closing
    word beside it and the row stays a notice.

    A YEAR THE TITLE LEAVES OUT is the first that puts the day on or after
    `anchor`, the row's own start or else its own edit date: IATA posted
    'Hunting Closure beginning 9/1' on 2026-08-17 (its date_posted, staged
    as the start), so 2026-09-01. Reasoned, not measured: a notice
    announces a start ahead of it, and one posted after the day it names
    reads the next year's day, the side that misses a closure rather than
    crosses a trail out early. No anchor and no year: no day. A two-digit
    year is 2000 and its digits. A day its month does not have is no day.

    @unvalidated beyond the live read of 2026-10-15, where 14 titles hold a
    start word: it reads IATA's '9/1' and '10/15' (posted 'yes'),
    Wisconsin DNR's 'Oct. 13, 2026' and 'Oct. 28, 2026' (both a park's
    water systems, a site) and King County's, whose own start field is
    already that day or later. What settles it is a person reading each
    title a later read holds beside the day this gives it.

    Example (int_closures__club_notices):

        {{ notice_title_start_day('title', 'title_start_word', 'starts_on') }}
-#}
{% macro notice_title_start_day(title, start_word, anchor) -%}
    {#- Groups: 1 month, 2 day and 3 year as numbers; 4 a month's name,
        5 its day and 6 its year. A part the title does not state is ''. -#}
    {%- set day_after -%}
        \s+(?:on\s+)?(?:([0-9]{1,2})/([0-9]{1,2})(?:/([0-9]{4}|[0-9]{2}))?|([a-z]+)\.?\s+([0-9]{1,2})(?:st|nd|rd|th)?(?:(?:\s*,\s*|\s+)([0-9]{4}))?)\b
    {%- endset -%}
    {%- set pattern = "'\\b' || " ~ start_word ~ " || '" ~ day_after ~ "'" -%}
    {%- set text = "lower(coalesce(" ~ title ~ ", ''))" -%}
    {%- set number_month = "regexp_extract(" ~ text ~ ", " ~ pattern ~ ", 1)" -%}
    {%- set number_day = "regexp_extract(" ~ text ~ ", " ~ pattern ~ ", 2)" -%}
    {%- set number_year = "regexp_extract(" ~ text ~ ", " ~ pattern ~ ", 3)" -%}
    {%- set named_month = "regexp_extract(" ~ text ~ ", " ~ pattern ~ ", 4)" -%}
    {%- set named_day = "regexp_extract(" ~ text ~ ", " ~ pattern ~ ", 5)" -%}
    {%- set named_year = "regexp_extract(" ~ text ~ ", " ~ pattern ~ ", 6)" -%}
    {%- set month = "coalesce(try_cast(nullif(" ~ number_month ~ ", '') as integer), "
        ~ notice_month_number(named_month) ~ ")" -%}
    {%- set day = "try_cast(nullif(coalesce(nullif(" ~ number_day ~ ", ''), "
        ~ named_day ~ "), '') as integer)" -%}
    {%- set year -%}
        case
            when length({{ number_year }}) = 2
                then 2000 + try_cast({{ number_year }} as integer)
            else
                try_cast(
                    nullif(coalesce(nullif({{ number_year }}, ''), {{ named_year }}), '')
                    as integer
                )
        end
    {%- endset -%}
    case
        when {{ start_word }} is null or {{ month }} is null or {{ day }} is null
            then null
        when {{ year }} is not null
            then {{ notice_stated_date(year, month, day) }}
        when {{ anchor }} is null then null
        when
            {{ notice_stated_date('year(' ~ anchor ~ ')', month, day) }}
            >= {{ anchor }}
            then {{ notice_stated_date('year(' ~ anchor ~ ')', month, day) }}
        else {{ notice_stated_date('year(' ~ anchor ~ ') + 1', month, day) }}
    end
{%- endmacro %}

{#- A month's number, 1 to 12, from its name or its three-letter
    abbreviation (or "sept"), as lowercase text; null for anything else. -#}
{% macro notice_month_number(name) -%}
    coalesce(
        list_position(
            ['january', 'february', 'march', 'april', 'may', 'june', 'july',
            'august', 'september', 'october', 'november', 'december'],
            {{ name }}
        ),
        list_position(
            ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep',
            'oct', 'nov', 'dec'],
            {{ name }}
        ),
        case when {{ name }} = 'sept' then 9 end
    )
{%- endmacro %}

{#- A DATE from a year, a month and a day as stated, or null where the
    calendar has no such day (February 30, a month 13). -#}
{% macro notice_stated_date(year, month, day) -%}
    try_cast(
        printf('%04d-%02d-%02d', {{ year }}, {{ month }}, {{ day }}) as date
    )
{%- endmacro %}
