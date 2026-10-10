{#-
    THE LAST DAY A NOTICE READS AS CURRENT (pipeline/ELT.md, "Status, water
    and expiry rules", rules 2 and 4), as conditions/notices.json publishes
    it in `current_until`: a DATE, or null where the row gives no date that
    bounds it. The phone compares this day with its own clock and greys the
    notice after it ("Last reported <date>. It may no longer apply.", or
    "Its source gives no date. It may no longer apply." for a null), so a
    phone that stays offline for days greys a notice on the day its date
    passes, which a build-time answer could not do. Never a hold: a notice
    past this day is still published (the maintainer's frame A, poll of
    2026-10-10).

    THE ORDER, the maintainer's "End date first" (poll of 2026-10-10), the
    first that applies:

    1. `ends_on`, the row's own end date: current through that day, whatever
       its edit date says.
    2. Rule 4's middle clause: the long end of a duration the row's own title
       states, counted from the row's own `starts_on`. "Lower loop closed for
       3 to 6 months" from 2025-01-06 is current through 2025-07-06. Only when
       the row carries both; notice_stated_duration_end() below is the
       parser, one rule for every source.
    3. The UTC day of `updated_at`, the source's own edit stamp as the file
       publishes it, plus var('notice_freshness_limit_days'): 90 days for
       every source (dbt_project.yml has it, and its @unvalidated note).
    4. Null: no date of any kind, so the phone never reads it as current. A
       start date alone bounds nothing, so a row with only a start, and no
       duration in its title, is null too.

    Inclusive of the day: a notice reads as current all through its last day,
    so a closure is shown as current a day too long rather than greyed a day
    early, the side a hiker in front of a closed trail is safer on
    (Reasoned).

    Example (pub_conditions_notices):

        strftime({{ notice_current_until('ends_on', 'starts_on', 'title', 'updated_at') }}, '%Y-%m-%d')
-#}
{% macro notice_current_until(ends_on, starts_on, title, updated_at) -%}
    {#- Each step is null where it does not apply, so the order is a coalesce. -#}
    coalesce(
        {{ ends_on }},
        {{ notice_stated_duration_end(starts_on, title) }},
        cast(timezone('UTC', try_cast({{ updated_at }} as timestamptz)) as date)
        + {{ var('notice_freshness_limit_days') }}
    )
{%- endmacro %}

{#-
    RULE 4's STATED DURATION, read from a title: the day its long end falls on
    when counted from `starts_on`, as a DATE, or null where the title states
    no duration this reads.

    NARROW ON PURPOSE, and one rule for every source. It reads a duration
    only after a closing word: "closed", "closes", "closing", "closure" or
    "closures", then up to four more words, then "for", an optional "about",
    "approximately", "approx.", "around", "roughly" or "up to", a number, an
    optional second number after "-", an en or em dash or "to", and a unit,
    "day", "week", "month" or "year", singular or plural. A number is 1 to 3
    digits or a word from "one" to "twelve", and case does not matter. So:

      "Lower loop closed for 3 to 6 months"       6 months
      "closed for approximately 3-6 months"       6 months (Portland's page)
      "Temporarily Closed for 4 to 5 Weeks"       5 weeks (King County's)
      "Bridge closure for two weeks"              2 weeks

    and nothing from "14 Day Stay Camping Limit Order" or "Five Year Burn Ban"
    (no closing word, no "for"), "closed for at least 6 months" (open-ended,
    so it has no long end), "closed for the season" (no number) or "Disclosed
    for 3 months" ("closed" has to start a word). A title this does not read
    falls through to the edit date, or to no date at all.

    @unvalidated: the four words, the hedges and the number words one to
    twelve were picked to read the examples above, not measured against
    enough titles to say what the pattern misses or misreads. What settles
    them is a person reading every title in a later notices.json that holds
    a number beside one of the units, which on 2026-10-10's file was 6 (the
    measurement below).

    THE LONG END: the larger of the two numbers. A day or a week adds days; a
    month or a year adds calendar months, which DuckDB clamps to the month's
    last day (2025-08-31 plus 6 months is 2026-02-28).

    Measured on UA's notices.json of 2026-10-10 17:24 UTC: 6 of its 8,305
    titles hold a number beside a day, week, month or year, 2 of those rows
    carry a start, and both carry an end date too, so this clause decides no
    row of that file. The unit tests on pub_conditions_notices hold what it
    reads and what it refuses.
-#}
{% macro notice_stated_duration_end(starts_on, title) -%}
    {#- The length is null where the title states no duration, which makes
        the whole sum null: no match, or no start, gives no day. -#}
    {%- set length = (
        "greatest("
        ~ notice_stated_number(notice_stated_duration_part(title, 1))
        ~ ", "
        ~ notice_stated_number(notice_stated_duration_part(title, 2))
        ~ ")"
    ) -%}
    {%- set unit = "lower(" ~ notice_stated_duration_part(title, 3) ~ ")" -%}
    cast(
        {{ starts_on }}
        + to_days({{ length }} * case {{ unit }} when 'day' then 1 when 'week' then 7 else 0 end)
        + to_months({{ length }} * case {{ unit }} when 'month' then 1 when 'year' then 12 else 0 end)
        as date
    )
{%- endmacro %}

{#- One capture of the duration pattern above, '' where it did not match:
    1 is the first number, 2 the second, 3 the unit. -#}
{% macro notice_stated_duration_part(title, group) -%}
    {%- set number = "[0-9]{1,3}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve" -%}
    regexp_extract(
        coalesce({{ title }}, ''),
        '(?i)\bclos(?:ed|es|ing|ure|ures)\b(?:[\s,:]+[a-z][a-z''-]*){0,4}?[\s,:]+for\s+(?:(?:about|approximately|approx\.|around|roughly|up\s+to)\s+)?({{ number }})(?:\s*(?:-|–|—|to)\s*({{ number }}))?[\s-]+(day|week|month|year)s?\b',
        {{ group }}
    )
{%- endmacro %}

{#- A number as the duration pattern captures it, digits or a word from one
    to twelve, as an INTEGER, or null for '' (no second number). -#}
{% macro notice_stated_number(text) -%}
    coalesce(
        try_cast({{ text }} as integer),
        list_position(
            ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve'],
            lower({{ text }})
        )
    )
{%- endmacro %}
