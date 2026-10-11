{#-
    RULE 1's DATE HOLDS, in one place for every notice row that carries the
    dates: int_closures__club_notices applies them to what this build read,
    and int_closures__held_carried to the rows it carries for a source the
    gate holds. int_closures__club_notices' header has the rule and why each
    margin errs toward showing a notice.

    TWO HOLDS, AND AN END DATE IS NOT ONE OF THEM. An order its source says
    was rescinded, and a notice whose own start is still more than a day
    away, are held back. A notice whose own end date has passed is NOT held
    (the maintainer's frame A, poll of 2026-10-10): it stays in the marts and
    in conditions/notices.json, whose `current_until`
    (macros/notice_current_until.sql) is that end date, so the phone greys
    it after that day. notice_has_ended() is what still reads the end date
    here, for rule 2: a status alone is never read as closing the trail once
    its own end has passed.

    `notice_build_date()` is the build's UTC date, or var
    `notices_build_date` where a unit test pins it (as
    int_challenges__items' `challenges_build_date` is pinned), so a test of
    a margin can name the days on either side of it. `notice_date_holds()` is
    the `when ... then <reason>` branches of a CASE, so a caller keeps its own
    branches before them; `rescinded_on` is optional, for a row that does not
    carry it (the marts do not).

    Example:

        case
            when status_reads = 'not_current' then 'its own status ...'
            {{ notice_date_holds('starts_on', notice_build_date(), 'rescinded_on') }}
        end as held_because
-#}
{% macro notice_build_date() -%}
    {%- set pinned = var('notices_build_date', none) -%}
    {%- if pinned -%}
        cast('{{ pinned }}' as date)
    {%- else -%}
        cast(timezone('UTC', now()) as date)
    {%- endif -%}
{%- endmacro %}

{% macro notice_date_holds(starts_on, build_date, rescinded_on=none) -%}
    {%- if rescinded_on %}
    when {{ rescinded_on }} is not null and {{ rescinded_on }} < {{ build_date }}
        then 'its own order was rescinded on ' || {{ rescinded_on }}
    {%- endif %}
    when {{ starts_on }} is not null and {{ starts_on }} > {{ build_date }} + 1
        then 'its own start date, ' || {{ starts_on }} || ', has not come'
{%- endmacro %}

{#- Whether a notice's own end day is more than one day behind the build's
    UTC date: true or false, never null. The same margin the end date had as
    a hold before 2026-10-10, for the reason int_closures__club_notices' rule
    1 gives: a day stated in a club's own zone has ended everywhere in the
    United States by 10:00 UTC the day after, so a closure reads as closing
    the trail a day too long rather than a day too short. -#}
{% macro notice_has_ended(ends_on, build_date) -%}
    coalesce({{ ends_on }} < {{ build_date }} - 1, false)
{%- endmacro %}
