{#-
    RULE 1's ONE DATE HOLD, in one place: int_closures__club_notices applies
    it to what this build read. int_closures__club_notices' header has the
    rule and why its margin errs toward showing a notice.

    ONE HOLD, A RESCINDED ORDER. An order its source says was rescinded is
    held back once the build's UTC date is past the UTC day of its
    rescission. Two dates that used to hold a notice back no longer do:
    - its own end date passing (the maintainer's frame A, poll of
      2026-10-10): the notice stays in the marts and in
      conditions/notices.json, whose `current_until`
      (macros/notice_current_until.sql) is that end date, so the phone greys
      it after that day. notice_has_ended() below is what still reads the
      end date, for rule 3: a notice is never read as closing the trail
      once its own end has passed;
    - its own start still ahead (the maintainer's frame B for wave 6's page
      01, P3, poll of 2026-10-11, "show it now, as upcoming"): the notice
      publishes now with its `starts_on`, and the phone's half of the same
      answer closes the trail only from the day before that day on its own
      calendar (int_closures__club_notices' rule 1).
    int_closures__held_carried calls nothing here: a carried row has no
    `rescinded_on` (it does not reach the marts), so this hold cannot fire
    on one.

    `notice_build_date()` is the build's UTC date, or var
    `notices_build_date` where a unit test pins it (as
    int_challenges__items' `challenges_build_date` is pinned), so a test of
    a margin can name the days on either side of it. `notice_date_holds()` is
    the `when ... then <reason>` branch of a CASE, so a caller keeps its own
    branches before it.

    Example:

        case
            when reads_as = 'not_current' then 'its own status ...'
            {{ notice_date_holds(notice_build_date(), 'rescinded_on') }}
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

{% macro notice_date_holds(build_date, rescinded_on) -%}
    when {{ rescinded_on }} is not null and {{ rescinded_on }} < {{ build_date }}
        then 'its own order was rescinded on ' || {{ rescinded_on }}
{%- endmacro %}

{#- Whether a notice's own end day is more than one day behind the build's
    UTC date: true or false, never null. The same margin the end date had as
    a hold before 2026-10-10, for the reason int_closures__club_notices' rule
    3 gives: a day stated in a club's own zone has ended everywhere in the
    United States by 11:00 UTC the day after (American Samoa, UTC-11, is the
    last zone to finish it), so a closure reads as closing the trail a day
    too long rather than a day too short. -#}
{% macro notice_has_ended(ends_on, build_date) -%}
    coalesce({{ ends_on }} < {{ build_date }} - 1, false)
{%- endmacro %}
