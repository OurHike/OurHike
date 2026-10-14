{{ config(materialized='table') }}
-- The trail stretches inside each area closure, or, where none runs inside,
-- the area itself as the map shades it. Decision 187 (S6, the maintainer's
-- poll of 2026-10-11): "an area closure's trails are crossed out where they
-- run inside it, cut by the hourly build as NYS Parks' areas already are
-- monthly". Decision 191 (the poll of 2026-10-14, "Shade them, no edge"): an
-- area closure with no mapped trail inside draws as a light hatch with no
-- mark on its edge. One row per area of int_closures__trail_closure_areas in
-- an hour that has lines to cut against: where a mapped trail runs inside,
-- `stretches` and their MultiLineString; where none does, `stretches` 0 and
-- `shade_geojson`, the area shaped for the phone.
-- pub_conditions_trail_closures puts one or the other in the closure's
-- `place`.
--
-- AN HOUR WITH NO LINES HAS NO ROW AT ALL. With nothing to cut against,
-- nothing says which areas have a trail inside, so none is shaded either:
-- the maintainer chose to shade only the areas with no trail inside, over
-- shading every area (decision 191's option B), and an area whose trails
-- would have been crossed out must not be drawn as one with none. So that
-- hour every area closure is left out of the file, as all of them were in
-- such an hour before decision 191, and step_closure_trail_lines' warning
-- says so. The step lands a row whenever it read lines (its docstring, "THE
-- TABLE IS EMPTY EXACTLY WHEN NO LINES WERE READ"), so an empty table means
-- exactly that hour.
--
-- THE LINES are every trail line a phone draws, from the environment's
-- current release (stg_derived__closure_trail_lines): its nearby trail lines
-- and, since decision 192 (the poll of 2026-10-14, "Yes, like any trail"),
-- the A.T.'s own, so a stretch is cut from the line drawn under it, the
-- A.T.'s included (prepare_closure_trail_lines.py says why).
--
-- THE RULE, int_trail_lines__network_area_closures' (export_nearby_trails.py's
-- apply_area_closures(), #964) on each area alone, with the same GEOS
-- operations: a line's part inside an area is its intersection with it,
-- reduced to the LineStrings of two or more distinct vertices it holds
-- (_line_parts(): a point where a trail only grazes the edge is not a
-- walkable section), so a line half inside keeps only its inside half. A
-- line on the edge is inside, as that rule has it: the GEOS intersection of a
-- line with a polygon keeps the part along its boundary.
--
-- SHAPED AS A PHONE NEEDS A LINE, by macros/notice_phone_geometry.sql, the
-- one home of that shape: Douglas-Peucker at 10 m with the topology kept, in
-- EPSG:5070, then 5 decimal places, as a line closure's own geometry is in
-- conditions/notices.json (pub_conditions_notices' header says why 10 m is
-- under a pixel at zoom 14). The stretches of one area are shaped together,
-- so none is moved across another. After the 5 decimal places a stretch can
-- be too short to keep two distinct vertices, so the rule above is applied
-- once more, and what is left is collected as a MultiLineString whatever its
-- count: one stretch is a MultiLineString of one, so a phone reads one type.
-- Measured 2026-10-11 against the 193 areas of UA's conditions/notices.json of
-- 16:23 UTC (grown 100 m, decision 77, so a little more than these areas)
-- and release 2026-10-10-2's lines: 47 of the 193 held a mapped trail, in
-- 1,311 stretches of 101,146 vertices, 2,203,651 bytes of GeoJSON at 5
-- decimals unshaped and 1,247,769 shaped at 10 m.
--
-- NO MAPPED TRAIL INSIDE means no stretch outlasts that: an area a trail
-- only grazes, or runs inside for under about a metre, is shaded, since
-- nothing in it could be drawn crossed out.
--
-- A SHADE IS THE AREA AS ITS SOURCE DREW IT, int_closures__trail_closure_areas'
-- own and never the 100 m grown outline notices.json carries, shaped by the
-- same macro ungrown (`grown=false`): the 10 m step in the macro's frame,
-- then 5 decimal places. A Polygon or a MultiPolygon, holes kept. An area
-- under about a metre across comes out empty and is left out: there is
-- nothing to shade.
--
-- NOTHING HERE STOPS THE HOURLY BUILD. This model builds in what
-- step_closure_trail_lines' table unblocks, where a failure would stop every
-- conditions file of the hour, not just this one (build_marts.py's docstring,
-- "ONE SOURCE OR ONE WRITER NEVER STOPS THE REST", isolates stage A's
-- per-source models and the writers alone). So each GEOS operation that can
-- raise is wrapped in TRY(), which on dbt 2.0.6's DuckDB 1.5.4 answers null
-- for an expression that raises (measured 2026-10-11 on a malformed polygon),
-- and an area any of whose cuts or shapes answers null has no row: it is
-- left out of the file and stays in notices.json's list. Never shaded: a
-- cut that raised says nothing about whether a trail runs inside.
with areas as (
    select
        notice_id,
        st_geomfromgeojson(area_geojson) as geom
    from {{ ref('int_closures__trail_closure_areas') }}
),

staged_lines as (
    select
        line_id,
        geom
    from {{ ref('stg_derived__closure_trail_lines') }}
),

-- One row when the hour read lines, none when it did not.
read_lines as (
    select count(*) as lines_read
    from staged_lines
    having count(*) > 0
),

lines as (
    select
        line_id,
        geom
    from staged_lines
    where geom is not null and not st_isempty(geom)
),

touching as (
    select
        areas.notice_id,
        lines.line_id,
        try(st_intersection(lines.geom, areas.geom)) as inside
    from areas
    inner join lines on st_intersects(lines.geom, areas.geom)
),

-- An area a line meets whose cut raised.
uncut as (
    select distinct notice_id
    from touching
    where inside is null
),

-- _line_parts(): each atomic piece, kept when it is a LineString of two or
-- more distinct vertices, which is exactly when its bounding box has a width
-- or a height.
pieces as (
    select
        notice_id,
        line_id,
        unnest(st_dump(inside)) as piece
    from touching
    where inside is not null
),

dumped as (
    select
        notice_id,
        line_id,
        struct_extract(piece, 'path') as part_path,
        struct_extract(piece, 'geom') as part
    from pieces
),

parts as (
    select *
    from dumped
    where
        st_geometrytype(part) = 'LINESTRING'
        and (st_xmin(part) < st_xmax(part) or st_ymin(part) < st_ymax(part))
),

stretches as (
    select
        notice_id,
        st_collect(list(part order by line_id, part_path)) as geom
    from parts
    group by notice_id
),

shaped as (
    select
        notice_id,
        try({{ notice_phone_geometry('geom') }}) as geom
    from stretches
),

-- An area whose stretches' shaping raised.
unshaped as (
    select notice_id
    from shaped
    where geom is null
),

shaped_pieces as (
    select
        notice_id,
        unnest(st_dump(geom)) as piece
    from shaped
    where geom is not null
),

shaped_dumped as (
    select
        notice_id,
        struct_extract(piece, 'path') as part_path,
        struct_extract(piece, 'geom') as part
    from shaped_pieces
),

shaped_parts as (
    select *
    from shaped_dumped
    where
        st_geometrytype(part) = 'LINESTRING'
        and (st_xmin(part) < st_xmax(part) or st_ymin(part) < st_ymax(part))
),

cuts as (
    select
        notice_id,
        count(*) as stretches,
        cast(
            st_asgeojson(st_collect(list(part order by part_path))) as varchar
        ) as stretches_geojson
    from shaped_parts
    group by notice_id
),

verdicts as (
    select
        areas.notice_id,
        coalesce(cuts.stretches, 0) as stretches,
        cuts.stretches_geojson,
        case
            when cuts.notice_id is null
                then try({{ notice_phone_geometry('areas.geom', grown=false) }})
        end as shade
    from areas
    cross join read_lines
    left join cuts on areas.notice_id = cuts.notice_id
    left join uncut on areas.notice_id = uncut.notice_id
    left join unshaped on areas.notice_id = unshaped.notice_id
    where uncut.notice_id is null and unshaped.notice_id is null
)

select
    notice_id,
    stretches,
    stretches_geojson,
    case
        when stretches = 0 then cast(st_asgeojson(shade) as varchar)
    end as shade_geojson
from verdicts
where
    stretches > 0
    or (shade is not null and not st_isempty(shade) and st_dimension(shade) = 2)
