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
-- inside it, a point closure as one cross; decision 191 (2026-10-14) shades
-- an area closure no mapped trail runs inside. The phone reads this file at
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
-- int_closures__club_notices' rule 1 has it, and holds a recurring season
-- until 30 days before it, decision 213's rule 9), and so is one the list greys
-- (decisions 146 and 150), at full strength (decision 187's fork, answered
-- "same mark"). The phone draws each from the day before its `starts_on` and
-- says on the sheet that a greyed one may no longer apply.
--
-- EACH ROW GAINS ONE KEY, `shape`, from the kind of the notice's own
-- geometry in that file: "line" for a LineString or MultiLineString, "point"
-- for a Point or MultiPoint, and for a Polygon or MultiPolygon "area" or
-- "shade". A line's or a point's `place` is unchanged. An area's `place`
-- becomes {"kind": "geometry", "geometry": ...}, cut against the area as the
-- source drew it, not the 100 m grown outline notices.json carries for a
-- planned route (int_closures__area_trail_cuts), and comes after the row's
-- other keys, just before `shape` (closure_rows says why):
-- - "area", where a mapped trail runs inside: the MultiLineString of the
--   trail stretches inside it, crossed out (decision 187);
-- - "shade", where none does: the area itself, a Polygon or MultiPolygon,
--   which the phone draws as a light hatch with no mark on its edge
--   (decision 191, the maintainer's poll of 2026-10-14, "Shade them, no
--   edge"). Until that decision such an area was left out of this file and
--   reached a hiker only through notices.json's list.
-- In an hour with no trail lines to cut against the cut has no row, and every
-- area closure is left out, neither crossed out nor shaded (the cut's header
-- says why), and the file says so (THE FILE SAYS WHETHER ITS AREAS WERE
-- CUT, below). A row with no geometry of those kinds (`unplaced`,
-- `org_terms`, a GeometryCollection) is left out too: there is nothing to
-- draw, and a guess would draw a closure where its source drew none.
--
-- THE SAME CLOSURE FROM TWO SOURCES IS DRAWN ONCE (the review of PR #1805
-- of 2026-10-15, thread 4279223668). Two drawn areas of different sources
-- that each cover at least `same_closure_share` of the other are one
-- closure posted twice, and drawing both stacks one hatch on another, with
-- a tap opening whichever sheet it finds. IDPR's area restrictions relay
-- other land managers' orders (all 20 rows read live 2026-10-15 name one
-- in JURISDICTION), and four were Region 4's own forest orders, drawn
-- twice until then: Calf Pen, Grimes Creek, Crooked Fire and Deer Point.
-- Each area is measured as its source drew it, the outline
-- int_closures__area_trail_cuts carries through from
-- int_closures__trail_closure_areas (`area_geojson`), in EPSG:5070 as the
-- cuts are, never notices.json's outline grown 100 m, which would make two
-- neighbours look alike. Of such a pair the file draws the row its source
-- edited first (`updated_at`; one with none counts as edited last), then the
-- lower notice_id: a copy is made after the order it copies, so the first
-- edit is the likelier original (Reasoned; on those four it keeps Region 4's
-- row three times, and IDPR's Crooked Fire, which IDPR posted two days
-- before Region 4's layer did). Which publisher's row to keep is the
-- maintainer's call, asked with the four pairs, so the rule names no source.
-- The other row is not drawn, and stays in notices.json's list under its
-- own credit.
-- ONLY AN AREA THE MAP DRAWS COMPETES: a row of the cut, which this file
-- crosses out or shades. An area the cut has no row for (its cut or its
-- shape raised, or it is under about a metre across) is drawn nowhere, so
-- it must not take a drawn copy's place. When the rule measured every area
-- of int_closures__trail_closure_areas instead, as it was first written,
-- such an area edited first hid the copy the cut had drawn, and neither was
-- drawn (this writer's unit test that
-- never_lets_an_undrawn_copy_edited_first_hide_the_drawn_one). In an hour
-- with no lines the cut has no row, so nothing competes and, as before, no
-- area is drawn.
-- @unvalidated: `same_closure_share`, 0.9, is the review's number. On the
-- live read of 2026-10-15 it matched exactly those four pairs (each covering
-- 0.993 to 1.000 of the other), and no other pair of areas of two sources
-- reached 0.5. What would settle it is a pair of different closures that
-- cover each other that much, which nobody has seen, or a copy redrawn
-- coarsely enough to fall below it. An intersection that raises compares
-- nothing, so both rows stay drawn: a duplicate hatch is the safer failure.
--
-- THE FILE SAYS WHETHER ITS AREAS WERE CUT THIS HOUR (decision 213, Q11, the
-- maintainer's poll of 2026-10-15, "Now, in this PR"), because a phone keeps
-- the last file it read as its offline copy, and one read in an hour with no
-- lines drew none of the area closures until it next connected: on UA,
-- whenever publish-weather.yml had no prepared lines to hand over, and in
-- production every hour until production's lines are prepared (#1811 —
-- Fast follows after PR #1805's dlt → dbt re-platform, section 5 of its
-- comment of 2026-10-14). Two keys beside `closures`:
-- - `areas_cut`, false when the file holds an area closure this hour and the
--   cut has no row at all, which is an hour with no lines or one where every
--   area's cut raised; true otherwise, an hour with no area closure
--   included, when there is nothing to cut and nothing a phone should keep.
-- - `uncut_areas`, the notice_id of every area closure in this hour's notices
--   that the file does not draw because its cut has no row: every one in an
--   hour that was not cut, and in one that was, an area whose own cut raised
--   or came out empty. Never one the same-closure rule left out, which is not
--   drawn on purpose. In notice_id order.
-- The phone (client/src/lib/publishedNotices.ts) keeps the last area or shade
-- it drew for each id listed and draws nothing for an id it never drew. A
-- closure lifted since is in no list, so it is dropped as soon as the file
-- that leaves it out arrives, as on any hour. Absent keys, a file written
-- before this, read as cut with nothing listed.
--
-- ORDER: by source_key, then notice_id, that writer's order.
--
-- SIZE. UA's first published file, of 2026-10-14 18:15 UTC, built before
-- decisions 191 and 192: 1,198 closures (975 lines, 46 areas, 177 points),
-- 3,165,161 bytes, 633,700 on the wire as its latest.json lists it. The 156
-- areas no mapped trail ran inside were left out of it. As shades they add
-- 197,598 bytes and 32,244 gzipped at level 6 (publish.py's), 5.1%: Measured
-- 2026-10-14 by adding them to that file with this build's shade, the
-- macro's `grown=false` expression, over their own outlines read live that
-- evening from the six layers (19,167 vertices, 4,486 after the 10 m step).
-- The decision was shown +134,995 bytes and +16,651 gzipped, reasoned from
-- notices.json's outlines, which are grown 100 m and simplified at 100 m.
-- Decision 192's A.T. stretches at Bear Mountain add about 600 bytes
-- (prepare_closure_trail_lines.py has them). The fixture build's file of the
-- same day: 25 closures (9 lines, 7 areas, 6 shades, 3 points), 17,499 bytes.
--
-- THE SAME WITHHOLDING. While pub_conditions_notices selects no row (a build
-- without the row history while a notice source is held), this selects none,
-- and the phone keeps its last copy. A build whose notices hold no closure
-- writes an empty list: the file arrived and no club closes a trail on the
-- map. An hour with no trail lines to cut against
-- (pipeline/step_closure_trail_lines.py) writes every line and point closure
-- and no area, `areas_cut` false, and its run summary says so.
{%- set same_closure_share = 0.9 %}
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
        stretches,
        stretches_geojson,
        shade_geojson,
        area_geojson
    from {{ ref('int_closures__area_trail_cuts') }}
),

-- Each drawn area's own outline, as its source drew it, in EPSG:5070: the
-- cut's rows are the areas this file draws, and only they compete.
outlines as (
    select
        notice_id,
        try(
            st_transform(
                st_geomfromgeojson(area_geojson),
                'EPSG:4326',
                'EPSG:5070',
                always_xy := true
            )
        ) as outline
    from cuts
),

areas as (
    select
        closing.notice_id,
        closing.source_key,
        coalesce(
            json_extract_string(closing.notice, '$.updated_at'), '9999'
        ) as edited,
        outlines.outline
    from closing
    inner join outlines on closing.notice_id = outlines.notice_id
    where
        closing.shape = 'area'
        and outlines.outline is not null
        and not st_isempty(outlines.outline)
),

-- Each pair of areas of two sources whose outlines meet, with what they
-- share.
meeting as (
    select
        first_area.notice_id as first_id,
        first_area.edited as first_edited,
        second_area.notice_id as second_id,
        second_area.edited as second_edited,
        st_area(first_area.outline) as first_area,
        st_area(second_area.outline) as second_area,
        try(
            st_area(st_intersection(first_area.outline, second_area.outline))
        ) as shared
    from areas as first_area
    inner join areas as second_area
        on
            first_area.source_key < second_area.source_key
            and st_intersects(first_area.outline, second_area.outline)
),

-- The row of each same-closure pair that is not drawn: the later edit, then
-- the higher notice_id.
not_drawn as (
    select distinct
        case
            when
                first_edited < second_edited
                or (first_edited = second_edited and first_id < second_id)
                then second_id
            else first_id
        end as notice_id
    from meeting
    where
        shared >= {{ same_closure_share }} * first_area
        and shared >= {{ same_closure_share }} * second_area
),

-- What each kept row is drawn as, and an area's new geometry.
placed as (
    select
        closing.source_key,
        closing.notice_id,
        closing.notice,
        case
            when closing.shape != 'area' then closing.shape
            when cuts.stretches > 0 then 'area'
            else 'shade'
        end as shape,
        case
            when cuts.stretches > 0 then cuts.stretches_geojson
            else cuts.shade_geojson
        end as area_geojson
    from closing
    left join cuts on closing.notice_id = cuts.notice_id
    left join not_drawn on closing.notice_id = not_drawn.notice_id
    where
        not_drawn.notice_id is null
        and (
            closing.shape in ('line', 'point')
            or (closing.shape = 'area' and cuts.notice_id is not null)
        )
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
        source_key,
        notice_id,
        case
            when shape in ('area', 'shade')
                then json_merge_patch(
                    json_merge_patch(notice, '{"place": null}'),
                    json_object(
                        'place',
                        json_object(
                            'kind',
                            'geometry',
                            'geometry',
                            cast(area_geojson as json)
                        ),
                        'shape',
                        shape
                    )
                )
            else json_merge_patch(notice, json_object('shape', shape))
        end as closure
    from placed
),

closures as (
    select list(closure order by source_key, notice_id) as closures
    from closure_rows
),

-- Every area closure of the hour the cut has no row for, the same-closure
-- rule's left-out row aside.
uncut as (
    select list(closing.notice_id order by closing.notice_id) as uncut_areas
    from closing
    left join cuts on closing.notice_id = cuts.notice_id
    where closing.shape = 'area' and cuts.notice_id is null
),

-- Whether the cut ran this hour, and whether there was an area to cut.
cut_hour as (
    select count(*) > 0 as any_cut
    from cuts
),

area_hour as (
    select count(*) > 0 as any_area
    from closing
    where shape = 'area'
)

select
    document.generated_at,
    coalesce(to_json(closures.closures), cast('[]' as json)) as closures,
    cut_hour.any_cut or not area_hour.any_area as areas_cut,
    coalesce(to_json(uncut.uncut_areas), cast('[]' as json)) as uncut_areas
from document
cross join closures
cross join cut_hour
cross join area_hour
cross join uncut
