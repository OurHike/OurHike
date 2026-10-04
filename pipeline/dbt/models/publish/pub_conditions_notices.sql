{{ config(
    format='json',
    location='conditions_notices.json',
    meta={'when_empty': 'keep_last_file'},
) }}
-- conditions/notices.json (decision 53, phase D; pipeline/ELT.md, "Phase D:
-- one notices file"): one OrgNotice (features/ORG_NOTICES.md section 2) per
-- club notice in the closures and warnings marts, every club in one file.
-- A club notice is a row of a source the extract declares a notice resource
-- for (seeds/notice_readers.csv): ATC's, NYNJTC's, NY Parks' closed areas and
-- every club's phase C notices. OurHike's own closures, its reports and
-- NWS's alerts have files of their own and are not here.
--
-- FACTS AND A LINK, NO PROSE (decision 55): a title, the club, its category,
-- the dates, the place and a link. Each value is a mart column, and
-- int_warnings__wording_leaks holds the marts to carrying none of a club's
-- paragraphs; NY Parks' closed areas, which have no title, take their own
-- `Name` (the mart's closure_reason), then the registry's title for the layer.
-- `steward_kind` is the readers seed's club or agency (decision 66's "clubs
-- only": the phone shows an agency's notice to a planned hike only where it
-- is placed on or near the route).
-- `states` is decision 76's: on the rows of a source seeds/notice_states.csv
-- names, the two-letter codes of the states it speaks for, and absent on
-- every other row. The phone shows such an agency notice to a hike planned
-- in one of them that walks the agency's trails, reading the states' shapes
-- from conditions/notice_states.json (pub_conditions_notice_states). The
-- place stays `unplaced`, so nothing is drawn.
-- `locality` is the source's own words for where, ATC's the states it names
-- (as lib/notices.ts's atcUpdateAsNotice joins them), and '' where it gives
-- none (ORG_NOTICES.md section 2: no locality, never a guess).
--
-- THE PLACE, features/ORG_NOTICES.md section 3's union, from the source's own
-- data and never inferred:
--   at_miles   ATC's rows, NOBO A.T. miles from Springer;
--   geometry   a row with its source's own geometry, simplified for a phone
--              (below);
--   org_terms  NYNJTC's trail and park tags as `taxonomy:slug`
--              (int_closures__nynjtc_checked), which place nothing until a
--              reviewed table maps a term to a feature (section 4);
--   unplaced   everything else.
--
-- THE GEOMETRY A PHONE NEEDS. Douglas-Peucker at 10 m, topology preserved,
-- in EPSG:5070 where a metre is a metre on both axes, then 6 decimal places
-- (decision 8). The phone draws an area and asks whether a trail meets it;
-- it never measures along it. 10 m is under one screen pixel at zoom 14 in
-- the lower 48 (a 256 px tile there spans about 1.7 km at 45 N, 6.8 m a
-- pixel), and inside the 4.5 to 11.45 m a phone's own fix is off under
-- canopy (ELT.md, "Simplify geometries"), so the boundary moves less than the
-- hiker's dot does (Reasoned). A part the simplification would empty keeps
-- its full shape. @unvalidated as a size: on the fixtures every geometry is
-- a few vertices, and how many bytes the live BAER and hunting polygons come
-- to at 10 m nobody has measured; the first UA build's file says.
--
-- THE DATES. `updated_at` is the club's own edit stamp, null where it gives
-- none. `checked_at` is OurHike's: the run log's (base_extract__runs) latest
-- read of the source that loaded it or found it unchanged, the oldest of
-- those across the source's tables, null where a table was never so read. On
-- a carried row (a source int_closures__gate holds this build keeps its last
-- good rows, int_closures__held_carried) it is the latest such read before
-- carrying began, so it never claims a read this build did not use.
-- `first_seen_at` and `changed_at` are the marts' row dates (decisions 52 and
-- 57), null in a build without its history (decision 58). `starts_on` and
-- `ends_on` are the club's own, never filled in.
--
-- DECISION 67'S HAZARD AREAS (seeds/notice_hazard_areas.csv) carry `hazard`
-- (hunting, shooting or burned_area) and never obstruct the trail. A burned
-- area is in the file while USFS's layer lists it: a full listing, so an area
-- USFS drops leaves on the next read (only a held read carries it, as every
-- notice is carried).
--
-- NEVER A CLUB EMPTIED BY ONE FAILED READ. A held source's rows are its last
-- good ones, from the marts. In a build without the row history
-- (OURHIKE_ROW_HISTORY=off), there is nothing to carry them from, so while
-- any notice source that may publish is held the writer selects no row and
-- the phone keeps its last file whole; with every source passing, it writes,
-- with the two row dates null.
--
-- `conditions/atc_updates.json` and `conditions/nynjtc_alerts.json` are not
-- touched: their writers, their parity lines and installed phones keep them
-- as they are (decision 51).
with readers as (
    select
        source_key,
        raw_table
    from {{ ref('notice_readers') }}
),

-- A source's tables all sit in one club folder, so one kind each.
notice_sources as (
    select
        source_key,
        any_value(steward_kind) as steward_kind
    from {{ ref('notice_readers') }}
    group by source_key
),

registry as (
    select
        source_key,
        provider,
        title as layer_title
    from {{ ref('stg_registry__sources') }}
),

hazards as (
    select
        source_key,
        any_value(hazard) as hazard
    from {{ ref('notice_hazard_areas') }}
    group by source_key
),

-- Decision 76's state-wide sources and the states each speaks for.
named_states as (
    select
        source_key,
        to_json(string_split(states, ' ')) as states
    from {{ ref('notice_states') }}
),

nynjtc_terms as (
    select
        notice_id,
        place_terms
    from {{ ref('int_closures__nynjtc_checked') }}
    where place_terms is not null
),

gate as (
    select * from {{ ref('int_closures__gate') }}
),

marts as (
    select
        closure_id as notice_id,
        club,
        source_key,
        obstructs_trail,
        review_state,
        coalesce(title, closure_reason) as title,
        category,
        coalesce(
            locality,
            closure_place,
            nullif(array_to_string(cast(states as varchar[]), ', '), '')
        ) as locality,
        mile_start,
        mile_end,
        starts_on,
        ends_on,
        updated_at,
        source_url,
        geom_geojson,
        _first_seen_at,
        _changed_at,
        carried_since
    from {{ ref('closures', v=1) }}
    union all by name
    select
        warning_id as notice_id,
        club,
        source_key,
        obstructs_trail,
        review_state,
        title,
        category,
        coalesce(
            locality,
            nullif(array_to_string(cast(states as varchar[]), ', '), '')
        ) as locality,
        mile_start,
        mile_end,
        starts_on,
        ends_on,
        updated_at,
        source_url,
        geom_geojson,
        _first_seen_at,
        _changed_at,
        carried_since
    from {{ ref('warnings', v=1) }}
    where warning_kind = 'org_notice'
),

club_notices as (
    select marts.*
    from marts
    inner join notice_sources on marts.source_key = notice_sources.source_key
),

-- A read that told OurHike what the source holds: one that loaded it, or
-- one whose change check found it unchanged (`skipped`, a FRESH verdict).
confirmations as (
    select
        readers.source_key,
        readers.raw_table,
        cast(runs.checked_at as timestamptz) as checked_at
    from readers
    inner join {{ ref('base_extract__runs') }} as runs
        on readers.raw_table = runs.table_name
    where runs.outcome in ('loaded', 'skipped')
),

table_checks as (
    select
        readers.source_key,
        readers.raw_table,
        max(confirmations.checked_at) as last_checked
    from readers
    left join confirmations on readers.raw_table = confirmations.raw_table
    group by readers.source_key, readers.raw_table
),

source_checks as (
    select
        source_key,
        case
            when bool_and(last_checked is not null) then min(last_checked)
        end as checked_at
    from table_checks
    group by source_key
),

carried_sources as (
    select distinct
        source_key,
        carried_since
    from club_notices
    where carried_since is not null
),

carried_table_checks as (
    select
        carried_sources.source_key,
        carried_sources.carried_since,
        readers.raw_table,
        max(confirmations.checked_at) as last_checked
    from carried_sources
    inner join readers on carried_sources.source_key = readers.source_key
    left join confirmations
        on
            readers.raw_table = confirmations.raw_table
            and carried_sources.carried_since > confirmations.checked_at
    group by
        carried_sources.source_key,
        carried_sources.carried_since,
        readers.raw_table
),

carried_checks as (
    select
        source_key,
        carried_since,
        case
            when bool_and(last_checked is not null) then min(last_checked)
        end as checked_at
    from carried_table_checks
    group by source_key, carried_since
),

-- Each geometry as a phone needs it (the header says why 10 m).
shaped as (
    select
        notice_id,
        st_geomfromgeojson(geom_geojson) as geom
    from club_notices
    where geom_geojson is not null
),

simplified as (
    select
        notice_id,
        geom,
        st_reduceprecision(
            st_transform(
                st_simplifypreservetopology(
                    st_transform(
                        geom, 'EPSG:4326', 'EPSG:5070', always_xy := true
                    ),
                    10
                ),
                'EPSG:5070',
                'EPSG:4326',
                always_xy := true
            ),
            0.000001
        ) as phone_geom
    from shaped
),

-- RFC 7946's ring order: GEOS's precision reducer and ST_Normalize wind a
-- polygon's shell clockwise and its holes counterclockwise, so ST_Reverse
-- gives the shell counterclockwise and the holes clockwise, as the RFC asks
-- of a writer (measured on DuckDB 1.5.5's spatial, 2026-10-04: a square
-- written either way came back counterclockwise, its hole clockwise).
placed as (
    select
        notice_id,
        cast(
            st_asgeojson(
                st_reverse(
                    st_normalize(
                        case
                            when phone_geom is null or st_isempty(phone_geom)
                                then st_reduceprecision(geom, 0.000001)
                            else phone_geom
                        end
                    )
                )
            ) as json
        ) as phone_geometry
    from simplified
),

notice_rows as (
    select
        club_notices.source_key,
        club_notices.notice_id,
        json_object(
            'notice_id', club_notices.notice_id,
            'source_key', club_notices.source_key,
            'club', club_notices.club,
            'provider', registry.provider,
            'steward_kind', notice_sources.steward_kind,
            'title', coalesce(club_notices.title, registry.layer_title),
            'category', club_notices.category,
            'locality', coalesce(club_notices.locality, ''),
            'place',
            case
                when
                    club_notices.source_key = 'atc_trail_updates'
                    and club_notices.mile_start is not null
                    and club_notices.mile_end is not null
                    then json_object(
                        'kind', 'at_miles',
                        'start', club_notices.mile_start,
                        'end', club_notices.mile_end
                    )
                when placed.phone_geometry is not null
                    then json_object(
                        'kind', 'geometry', 'geometry', placed.phone_geometry
                    )
                when nynjtc_terms.place_terms is not null
                    then json_object(
                        'kind', 'org_terms',
                        'terms', cast(nynjtc_terms.place_terms as json)
                    )
                else json_object('kind', 'unplaced')
            end,
            'hazard', hazards.hazard,
            'obstructs_trail',
            coalesce(club_notices.obstructs_trail, false)
            and hazards.hazard is null,
            'starts_on', strftime(club_notices.starts_on, '%Y-%m-%d'),
            'ends_on', strftime(club_notices.ends_on, '%Y-%m-%d'),
            'updated_at', club_notices.updated_at,
            'checked_at',
            {{ python_utc_seconds(
                'case when club_notices.carried_since is null'
                ~ ' then source_checks.checked_at'
                ~ ' else carried_checks.checked_at end'
            ) }},
            'first_seen_at',
            {{ python_utc_seconds('club_notices._first_seen_at') }},
            'changed_at', {{ python_utc_seconds('club_notices._changed_at') }},
            'carried_since',
            {{ python_utc_seconds('club_notices.carried_since') }},
            'source_url', club_notices.source_url,
            'review_state',
            case
                when club_notices.review_state = 'reviewed' then 'reviewed'
                else 'unreviewed'
            end
        ) as notice
    from club_notices
    inner join notice_sources
        on club_notices.source_key = notice_sources.source_key
    left join registry on club_notices.source_key = registry.source_key
    left join hazards on club_notices.source_key = hazards.source_key
    left join nynjtc_terms on club_notices.notice_id = nynjtc_terms.notice_id
    left join placed on club_notices.notice_id = placed.notice_id
    left join source_checks
        on club_notices.source_key = source_checks.source_key
    left join carried_checks
        on
            club_notices.source_key = carried_checks.source_key
            and club_notices.carried_since = carried_checks.carried_since
),

-- Decision 76's `states` (seeds/notice_states.csv), on a state-wide source's
-- rows only, so no other row carries a null for it.
stated_rows as (
    select
        notice_rows.source_key,
        notice_rows.notice_id,
        case
            when named_states.states is null then notice_rows.notice
            else
                json_merge_patch(
                    notice_rows.notice,
                    json_object('states', named_states.states)
                )
        end as notice
    from notice_rows
    left join named_states on notice_rows.source_key = named_states.source_key
),

-- Whether a notice source that may publish is held this build: in a build
-- without the row history its last good rows cannot be carried.
held as (
    select count(*) as sources_held
    from gate
    inner join notice_sources on gate.source_key = notice_sources.source_key
    where not gate.passed and gate.may_publish
),

-- One JSON value rather than a list column, so its unit tests can read it
-- (a 2.0.6 unit test refuses a list column in a model's output, the dbt
-- skill's contract traps); phone_file writes it into the document as the
-- same array either way.
published as (
    select
        coalesce(
            to_json(
                list(
                    stated_rows.notice
                    order by stated_rows.source_key, stated_rows.notice_id
                )
            ),
            cast('[]' as json)
        ) as notices
    from stated_rows
)

select
    {{ python_run_stamp() }} as generated_at,
    published.notices
from published
cross join held
{{ when_row_history_is_off('where held.sources_held = 0') }}
