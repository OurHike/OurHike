{{ config(materialized='table') }}
-- The trail stretches inside each area closure: decision 187 (S6, the
-- maintainer's poll of 2026-10-11), "an area closure's trails are crossed
-- out where they run inside it, cut by the hourly build as NYS Parks' areas
-- already are monthly". One row per area of int_closures__trail_closure_areas
-- that a mapped trail runs inside, its stretches one MultiLineString;
-- pub_conditions_trail_closures puts it in that closure's `place`, and an
-- area no trail runs inside has no row here and stays out of that file.
--
-- THE LINES are the environment's current release's nearby trail lines
-- (stg_derived__closure_trail_lines), the layer a phone draws every nearby
-- trail from, so a stretch is cut from the line drawn under it.
-- prepare_closure_trail_lines.py says why not the A.T.'s own lines.
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
-- NOTHING HERE STOPS THE HOURLY BUILD. This model builds in what
-- step_closure_trail_lines' table unblocks, where a failure would stop every
-- conditions file of the hour, not just this one (build_marts.py's docstring,
-- "ONE SOURCE OR ONE WRITER NEVER STOPS THE REST", isolates stage A's
-- per-source models and the writers alone). So each GEOS operation that can
-- raise is wrapped in TRY(), which on dbt 2.0.6's DuckDB 1.5.4 answers null
-- for an expression that raises (measured 2026-10-11 on a malformed polygon),
-- and an area whose cut answers null has no row: it is left out of the file,
-- as an area with no trail inside is, and stays in notices.json's list.
with areas as (
    select
        notice_id,
        st_geomfromgeojson(area_geojson) as geom
    from {{ ref('int_closures__trail_closure_areas') }}
),

lines as (
    select
        line_id,
        geom
    from {{ ref('stg_derived__closure_trail_lines') }}
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
)

select
    notice_id,
    count(*) as stretches,
    cast(
        st_asgeojson(st_collect(list(part order by part_path))) as varchar
    ) as stretches_geojson
from shaped_parts
group by notice_id
