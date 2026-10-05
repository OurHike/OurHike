{#-
    RULE 1's DATE HOLDS, in one place for every notice row that carries the
    dates: int_closures__club_notices applies them to what this build read,
    and int_closures__held_carried to the rows it carries for a source the
    gate holds, so a carried notice leaves the marts when its own end passes,
    as a fresh one does. int_closures__club_notices' header has the rule and
    why each margin errs toward showing a notice.

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
            {{ notice_date_holds('starts_on', 'ends_on', notice_build_date(), 'rescinded_on') }}
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

{% macro notice_date_holds(starts_on, ends_on, build_date, rescinded_on=none) -%}
    {%- if rescinded_on %}
    when {{ rescinded_on }} is not null and {{ rescinded_on }} <= {{ build_date }}
        then 'its own order was rescinded on ' || {{ rescinded_on }}
    {%- endif %}
    when {{ ends_on }} is not null and {{ ends_on }} < {{ build_date }} - 1
        then 'its own end date, ' || {{ ends_on }} || ', has passed'
    when {{ starts_on }} is not null and {{ starts_on }} > {{ build_date }} + 1
        then 'its own start date, ' || {{ starts_on }} || ', has not come'
{%- endmacro %}
