{{ config(materialized='table') }}
-- Every generated club notice source's rows
-- (int_closures__club_notices_unioned, pipeline/generate_notice_models.py),
-- read by decision 53's phase C rules
-- (pipeline/ELT.md, "Every club's closures and alerts", phase C): one row per
-- notice, in the closures family's columns, with whether it blocks the trail
-- and, where it may not publish as current, why. Nothing is dropped here; the
-- finals leave out a row whose `held_because` is set, so the reason stays
-- readable in the warehouse.
--
-- THE RULES, each held by a unit test in _closures__intermediate.yml:
--
-- 1. A NOTICE IS KEPT WHATEVER ITS OWN DATES SAY.
--    ONE WHOSE STATED END HAS PASSED is never read as current. The
--    maintainer's frame A (poll of 2026-10-10): a notice past its own end
--    date stays in the list, greyed, rather than leaving it. Until then this
--    rule held such a notice back, so UA's notices.json of 2026-10-10 17:24
--    UTC carried none of them: 0 of its 1,464 rows with an end date had one
--    already past. Standing Stone's closure pages, which still serve
--    closures that ended in 2022 and 2023 (phase A), now reach a phone that
--    way. conditions/notices.json's `current_until` is that end day
--    (macros/notice_current_until.sql), and the phone greys the notice after
--    it on its own clock, so a phone offline for days greys it on the day,
--    which a build-time hold could not. Rule 2 below still reads it. Its end
--    is the day of `ends_at` in UTC.
--    ONE WHOSE OWN START IS STILL AHEAD PUBLISHES NOW, AS UPCOMING: the
--    maintainer's frame B for wave 6's page 01, P3 (poll of 2026-10-11, "show
--    it now, as upcoming"). Until then this rule held it while its UTC start
--    day was more than one day ahead (Yellowstone's bear management areas,
--    New Jersey's WMA restrictions, King County's alerts and IDPR's emergency
--    closures state one), so a phone that last connected before that day
--    never showed it. It now carries its own `starts_on`, and
--    `obstructs_trail` is rule 2's, read without regard to the start: a
--    closure that starts next month publishes `obstructs_trail` true today.
--    THE PHONE DECIDES THE DAY IT CLOSES, the other half of the same answer:
--    it draws the trail closed only from the day before `starts_on` on its
--    own calendar, and tags the notice "Starts <date>" until then. The day
--    before, because `starts_on` is the UTC day of the source's start
--    instant, and an instant stated in a United States zone (UTC-4 to
--    UTC-10) falls in that zone on that UTC day or the day before it, never
--    after; so a phone in the trail's zone closes the trail up to a day
--    early, never a day late (Reasoned from the zones' offsets, not measured
--    on any source). A start the source states as a day alone (an ArcGIS
--    DateOnly field, or epoch milliseconds at UTC midnight) is that day, and
--    the phone closes the trail the whole day before it. `current_until` is
--    not moved by the start (macros/notice_current_until.sql: its own end
--    first), so an upcoming notice with no end and no edit date carries a
--    null one; until its start the phone's tag says what it is.
--    ONE DATE STILL HOLDS A NOTICE BACK (macros/notice_date_holds.sql): an
--    order the source says was rescinded is held, once the build's UTC date
--    is past the UTC day of its rescission. That is the source's own word
--    that the order was lifted, as a status is, not a date OurHike reads an
--    expiry from. An order is lifted at that instant, not at the end of a
--    stated day, and the first build to hold it starts at 00:00 UTC the next
--    day, after the instant whatever the zone it was stated in. So it rounds
--    toward showing an order up to a day after it was lifted, never hiding
--    one still in force (Reasoned, not measured on any source; with no
--    margin, before 2026-10-05, a Denver order rescinded at local midnight
--    was held from 18:00 local the evening before).
-- 2. A STATUS ALONE IS NEVER READ AS CLOSED NOW WHEN ITS OWN END HAS PASSED.
--    `obstructs_trail` is true only where the source's own status field
--    holds a value seeds/notice_status_values.csv reads as `closes_trail`,
--    the source files the notice under closures (its club's closures.py),
--    rule 1 does not hold it, and its own end day is not more than one day
--    behind the build's UTC date (macros/notice_date_holds.sql's
--    notice_has_ended(): a day stated in a club's own zone has ended
--    everywhere in the United States, UTC-4 to UTC-10, by 10:00 UTC the day
--    after, so the margin reads a closure as closing a day too long, never a
--    day too short; Reasoned, not measured on any source). The USFS R06 fire
--    closures carried 'Active' beside an end date already past on 112 of 938
--    lines, and CDPR 'Full Closure' beside a passed StatusReopenDate is the
--    same shape (pipeline/ELT.md, "Status, water and expiry rules", rule 1).
--    Everything else is null, which decision 7 lands in warnings as not
--    reviewed: miss rather than cry wolf. So a notice past its end lands in
--    warnings, kept and not current, never in closures.
-- 3. A STATUS THE SOURCE USES FOR "NOT CURRENT" HOLDS THE ROW: an inactive
--    flag (CDTC's Active No, Wisconsin DNR's Active_Flag No), an unposted
--    one (IATA's posted no), or an open one, which tells a hiker nothing.
-- 4. PLACE ONLY FROM THE SOURCE'S OWN GEOMETRY. `geom_geojson` is the
--    staging model's own geometry, never a match of `locality` or a title
--    against a place table: a notice with none is unplaced, and its
--    locality is the source's own words for where (ORG_NOTICES.md section
--    3). A reviewed term table, the other way phase C allows, does not
--    exist for any of these sources yet.
-- 5. FACTS AND A LINK (decision 55). The columns are the notice's title,
--    category, dates, place and link; no prose column exists to carry, and
--    int_warnings__wording_leaks fails the build if one reaches a mart.
-- 6. A HAZARD AREA IS ONLY THE HAZARD ITS OWN CATEGORY SAYS (decision 67).
--    A source seeds/notice_hazard_areas.csv lists with category values
--    publishes only the rows whose own category is one of them: IATA's
--    'No hunting' parcels and NY Parks' safety zones are where hunting is
--    not allowed, and drawing one as a hunting area would tell a hiker the
--    opposite of what the layer says. The rest are held with the category
--    in the reason. A source listed with no category value publishes every
--    row. Its dates are its own (`starts_on`, `ends_on`), and a layer with
--    no season field has none: none of the four hunting layers gives one
--    (seeds/notice_source_fields.csv), so their dates are null, never a
--    season OurHike supplied.
--
-- `key_versions` is how many different raw rows share the notice's key (its
-- base model counts them); int_closures__gate holds a source with any over
-- one.
--
-- `updated_at` is the source's own edit stamp, in ISO 8601 UTC, and null
-- where it gives none: never the load time. `notice_id` is
-- `<source key>:<the source's own id>` (features/ORG_NOTICES.md section 2).
with notices as (
    select * from {{ ref('int_closures__club_notices_unioned') }}
),

status_values as (
    select * from {{ ref('notice_status_values') }}
),

-- Rule 6's seed: each hazard source once, with whether every row is the
-- hazard, and its category values as compared.
hazard_sources as (
    select
        source_key,
        any_value(hazard) as hazard,
        bool_or(coalesce(trim(category_value), '') = '') as every_row
    from {{ ref('notice_hazard_areas') }}
    group by source_key
),

hazard_values as (
    select distinct
        source_key,
        lower(trim(category_value)) as category_value
    from {{ ref('notice_hazard_areas') }}
    where coalesce(trim(category_value), '') != ''
),

read_status as (
    select
        notices.*,
        status_values.reads_as as status_reads,
        hazard_sources.hazard,
        coalesce(hazard_sources.every_row, false) as hazard_every_row,
        hazard_values.category_value is not null as hazard_category_listed,
        cast(timezone('UTC', notices.starts_at) as date) as starts_on,
        cast(timezone('UTC', notices.ends_at) as date) as ends_on,
        cast(timezone('UTC', notices.rescinded_at) as date) as rescinded_on,
        {{ notice_build_date() }} as build_date
    from notices
    left join status_values
        on
            notices.source_key = status_values.source_key
            and lower(trim(notices.status)) = lower(status_values.status_value)
    left join hazard_sources
        on notices.source_key = hazard_sources.source_key
    left join hazard_values
        on
            notices.source_key = hazard_values.source_key
            and lower(trim(notices.category)) = hazard_values.category_value
),

-- Rule 1's one date hold comes last, from macros/notice_date_holds.sql;
-- rule 2's end date is `has_ended`, which holds nothing back.
judged as (
    select
        *,
        case
            when status_reads = 'not_current'
                then
                    'its own status reads ' || status
                    || ', which the source uses for a notice that is not '
                    || 'current'
            when
                hazard is not null
                and not hazard_every_row
                and not hazard_category_listed
                then
                    'its own category, ' || coalesce(category, 'none')
                    || ', is not one notice_hazard_areas reads as '
                    || hazard
            {{ notice_date_holds('build_date', 'rescinded_on') }}
        end as held_because,
        {{ notice_has_ended('ends_on', 'build_date') }} as has_ended
    from read_status
)

select
    source_key || ':' || coalesce(source_id, 'key-' || notice_key) as notice_id,
    notice_key as source_row_key,
    'club_' || reader as notice_kind,
    club,
    source_key,
    notice_type,
    listing,
    case
        when
            notice_type = 'closures'
            and status_reads = 'closes_trail'
            and held_because is null
            and not has_ended
            then true
    end as obstructs_trail,
    case
        when
            notice_type = 'closures'
            and status_reads = 'closes_trail'
            and held_because is null
            and not has_ended
            then 'org_published'
        else 'not_reviewed'
    end as review_state,
    {{ python_html_unescape('title') }} as title,
    category,
    status,
    status_reads,
    locality,
    starts_at,
    starts_on,
    ends_on,
    rescinded_on,
    source_edited_at,
    strftime(timezone('UTC', source_edited_at), '%Y-%m-%dT%H:%M:%SZ')
        as updated_at,
    source_url,
    geom_geojson,
    held_because,
    key_versions,
    _loaded_at
from judged
