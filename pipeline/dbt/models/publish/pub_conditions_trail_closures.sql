{{ config(
    format='json',
    location='conditions_trail_closures.json',
    meta={'when_empty': 'keep_last_file'},
) }}
-- conditions/trail_closures.json: every club closure, for the map. Decision
-- 184 (the maintainer's poll of 2026-10-11, "Build the map file now") builds
-- #1152 — Move OPRHP's temporary closures onto the conditions clock, where a
-- safety layer belongs — in its shape (C), an hourly file of closed
-- stretches, for every club closure in PR #1805, and decision 187 (S6) says
-- how each is drawn with the crossed-out mark (client/src/lib/closureStyle.ts):
-- a line closure along its own line, an area closure's trails where they run
-- inside it, a point closure as one cross. The phone reads this file at
-- launch, as it reads conditions/hazard_areas.json (decision 84), because
-- decision 77 downloads notices.json only once a hike is planned. Routes
-- still go through a closure: this file changes what is drawn, not where a
-- route may run.
--
-- ONE HOME FOR EVERY RULE, as pub_conditions_hazard_areas has it: this
-- selects from pub_conditions_notices' own table and keeps each row exactly
-- as that writer wrote it, so which rows obstruct a trail, the row shape
-- (features/ORG_NOTICES.md section 2), the phone geometry, the dates, the
-- carried rows of a held source and `states` are that writer's, and nothing
-- here can drift from them. `generated_at` is that writer's stamp.
--
-- WHICH ROWS: every notice whose `obstructs_trail` is true, so never one of
-- decision 67's hazard areas, which that writer never marks obstructing; but
-- not ATC's own (`atc_trail_updates`), whose band the phone already draws
-- from conditions/atc_updates.json. No date decides it: a closure whose start
-- is still ahead is here (decision 167, "show it now, as upcoming";
-- int_closures__club_notices' rule 1 has it), and so is one the list greys
-- (decisions 146 and 150), at full strength (decision 187's fork, answered
-- "same mark"). The phone draws each from the day before its `starts_on` and
-- says on the sheet that a greyed one may no longer apply.
--
-- EACH ROW GAINS ONE KEY, `shape`, from the kind of the notice's own
-- geometry in that file: "line" for a LineString or MultiLineString, "point"
-- for a Point or MultiPoint, "area" for a Polygon or MultiPolygon. A line's
-- or a point's `place` is unchanged. An area's `place` becomes
-- {"kind": "geometry", "geometry": <MultiLineString>}, the mapped trail
-- stretches inside it (int_closures__area_trail_cuts, cut against the area
-- as the source drew it, not the 100 m grown outline notices.json carries
-- for a planned route), and comes after the row's other keys, just before
-- `shape` (closure_rows says why); an area no mapped trail runs inside is
-- left out of this file, and stays in notices.json's list. A row with no
-- geometry of those kinds (`unplaced`, `org_terms`, a GeometryCollection) is
-- left out too: there is nothing to cross out, and a guess would draw a
-- closure where its source drew none.
--
-- ORDER: by source_key, then notice_id, that writer's order.
--
-- SIZE, Measured 2026-10-14 with this SQL and int_closures__area_trail_cuts'
-- as dbt compiles them, run on DuckDB 1.5.5, over UA's conditions/notices.json
-- of 2026-10-11 16:23 UTC and release 2026-10-10-2's nearby trail lines (both
-- read 2026-10-11): 1,108 closures (888 lines, 47 areas, 173 points),
-- 3,123,994 bytes and 630,688 gzipped at level 6 (publish.py's), 1,246,300 of
-- the bytes the 47 areas' stretches. Those areas were the file's own 100 m
-- grown outlines, larger than the source areas this build cuts against, so
-- the area half is an upper bound; the 146 areas no mapped trail ran inside
-- were left out. The fixture build's file: 18 closures, 12,367 bytes.
--
-- THE SAME WITHHOLDING. While pub_conditions_notices selects no row (a build
-- without the row history while a notice source is held), this selects none,
-- and the phone keeps its last copy. A build whose notices hold no closure
-- writes an empty list: the file arrived and no club closes a trail on the
-- map. An hour with no trail lines to cut against
-- (pipeline/step_closure_trail_lines.py) writes every line and point closure
-- and no area, and its run summary says so.
with document as (
    select
        generated_at,
        notices
    from {{ ref('pub_conditions_notices') }}
),

notice_rows as (
    select unnest(cast(notices as json[])) as notice
    from document
),

closing as (
    select
        notice,
        json_extract_string(notice, '$.source_key') as source_key,
        json_extract_string(notice, '$.notice_id') as notice_id,
        case json_extract_string(notice, '$.place.geometry.type')
            when 'LineString' then 'line'
            when 'MultiLineString' then 'line'
            when 'Point' then 'point'
            when 'MultiPoint' then 'point'
            when 'Polygon' then 'area'
            when 'MultiPolygon' then 'area'
        end as shape
    from notice_rows
    where
        json_extract_string(notice, '$.obstructs_trail') = 'true'
        and json_extract_string(notice, '$.source_key') != 'atc_trail_updates'
        and json_extract_string(notice, '$.place.kind') = 'geometry'
),

cuts as (
    select
        notice_id,
        stretches_geojson
    from {{ ref('int_closures__area_trail_cuts') }}
),

-- json_merge_patch is RFC 7386's merge patch, and a null in the patch removes
-- a key: an area's `place` is removed whole and written again, so no part of
-- the area's outline can survive beside its stretches. DuckDB's merge patch
-- writes a key the patch sets after the keys it leaves alone, so `shape`
-- comes last on every row and an area's new `place` just before it (Measured
-- 2026-10-11 on dbt 2.0.6's DuckDB 1.5.4, in this model's unit test). A JSON
-- object's keys carry no order (RFC 8259), so a reader sees the same row.
closure_rows as (
    select
        closing.source_key,
        closing.notice_id,
        case
            when closing.shape = 'area'
                then json_merge_patch(
                    json_merge_patch(closing.notice, '{"place": null}'),
                    json_object(
                        'place',
                        json_object(
                            'kind',
                            'geometry',
                            'geometry',
                            cast(cuts.stretches_geojson as json)
                        ),
                        'shape',
                        closing.shape
                    )
                )
            else json_merge_patch(
                closing.notice, json_object('shape', closing.shape)
            )
        end as closure
    from closing
    left join cuts on closing.notice_id = cuts.notice_id
    where
        closing.shape in ('line', 'point')
        or (closing.shape = 'area' and cuts.notice_id is not null)
),

closures as (
    select list(closure order by source_key, notice_id) as closures
    from closure_rows
)

select
    document.generated_at,
    coalesce(to_json(closures.closures), cast('[]' as json)) as closures
from document
cross join closures
