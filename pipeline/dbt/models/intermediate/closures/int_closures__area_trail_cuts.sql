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
-- EVERY ROW CARRIES ITS AREA'S OWN OUTLINE, `area_geojson`, exactly as
-- int_closures__trail_closure_areas gives it, for
-- pub_conditions_trail_closures' same-closure rule (its header, "THE SAME
-- CLOSURE FROM TWO SOURCES IS DRAWN ONCE"): that writer compares only the
-- areas it draws, which are this model's rows, so it reads their outlines
-- here. Reading them from the areas model as well, which this model already
-- reads, is the rejoin dbt_project_evaluator's
-- fct_rejoining_of_upstream_concepts fails.
--
-- AN HOUR WITH NO LINES HAS NO ROW AT ALL. With nothing to cut against,
-- nothing says which areas have a trail inside, so none is shaded either:
-- the maintainer chose to shade only the areas with no trail inside, over
-- shading every area (the option B), and an area whose trails
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
-- apply_area_closures(), from #964 — NYS Parks closes areas, not trail
-- segments, and the closure model has nowhere to put one) on each area
-- alone, with the same GEOS operations: a line's part inside an area is its
-- intersection with it, reduced to the LineStrings of two or more distinct
-- vertices it holds (_line_parts(): a point where a trail only grazes the
-- edge is not a walkable section), so a line half inside keeps only its
-- inside half.
--
-- ONLY A STRETCH INSIDE THE AREA CLOSES, NOT ONE ALONG ITS EDGE (decision
-- 213, rule 6, the maintainer's poll of 2026-10-15, "Only inside closes",
-- for every source). The GEOS intersection of a line with a polygon keeps
-- the part along its boundary, so a trail that forms an area's edge was
-- crossed out, and in fragments: the lines are rounded to 5 decimal places
-- before the cut and the areas are not, so such a trail weaves across the
-- edge and the cut keeps each piece on the inside. Decision 191 meant an
-- open trail along an edge never to read as closed. So a stretch closes
-- only if some part of it lies more than `area_closure_edge_m` (2 m,
-- dbt_project.yml says whose number it is) in from the area's outline, a
-- hole's edge included, measured in EPSG:5070 as the cuts' other distances
-- are; one lying wholly within that band of the outline is left out of the
-- stretches. The test is on each piece as the cut leaves it, so the
-- vertices of every stretch that closes are still the cut's own. A piece
-- that runs along the edge and then turns inside closes whole, its edge part
-- with it. Measured 2026-10-15 on UA's live areas against release
-- 2026-10-10-2's lines, prepared as prepare_closure_trail_lines.py prepares
-- them. The areas: every one conditions/trail_closures.json of 21:26 UTC
-- drew, crossed out or shaded, of the ten sources it crossed one out for,
-- each read from its source's layer that evening, 208 areas, 130 of them
-- with a piece inside (the file crossed out 131; one of IDPR's was gone from
-- its layer). 5,090 pieces lay inside, 3,554.09 miles. 1,197 of them (36.96
-- miles) had their midpoint within 2 m of the outline, and 1,081 (25.99
-- miles) lay wholly within 2 m, which this leaves open: 794 of those (22.28
-- miles) in USFS Region 6's fire closures. 5 of COTREX's areas, every piece
-- of which lay along an edge, turn from crossed out to shaded. The 116
-- pieces whose midpoint is near the outline but which reach further in stay
-- closed. Miles are lengths in EPSG:5070, before the 10 m shaping. The same
-- cut in DuckDB 1.5.5 on 2 threads of a loaded sandbox found the same 1,081
-- and took 5.9 s against 4.0 s without the band.
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
-- 16:23 UTC (grown 100 m, so a little more than these areas)
-- and release 2026-10-10-2's lines: 47 of the 193 held a mapped trail, in
-- 1,311 stretches of 101,146 vertices, 2,203,651 bytes of GeoJSON at 5
-- decimals unshaped and 1,247,769 shaped at 10 m.
--
-- NO MAPPED TRAIL INSIDE means no stretch outlasts that: an area a trail
-- only grazes, runs along within 2 m of its edge, or runs inside for under
-- about a metre, is shaded, since nothing in it could be drawn crossed out.
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
with outlined as (
    select
        notice_id,
        area_geojson,
        st_geomfromgeojson(area_geojson) as geom
    from {{ ref('int_closures__trail_closure_areas') }}
),

-- Each area with the band within `area_closure_edge_m` of its outline, in
-- EPSG:5070 (rule 6 above).
areas as (
    select
        notice_id,
        area_geojson,
        geom,
        try(
            st_buffer(
                st_transform(
                    st_boundary(geom),
                    'EPSG:4326',
                    'EPSG:5070',
                    always_xy := true
                ),
                {{ var('area_closure_edge_m') }}
            )
        ) as edge_band
    from outlined
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

-- Each walkable piece, and whether it lies wholly within the band along its
-- area's outline (rule 6): null where that could not be measured. The band
-- is joined here rather than carried through the unnest above, so each
-- area's band is not copied onto every piece's row.
parts as (
    select
        dumped.notice_id,
        dumped.line_id,
        dumped.part_path,
        dumped.part,
        try(
            st_covers(
                areas.edge_band,
                st_transform(
                    dumped.part, 'EPSG:4326', 'EPSG:5070', always_xy := true
                )
            )
        ) as along_edge
    from dumped
    inner join areas on dumped.notice_id = areas.notice_id
    where
        st_geometrytype(dumped.part) = 'LINESTRING'
        and (
            st_xmin(dumped.part) < st_xmax(dumped.part)
            or st_ymin(dumped.part) < st_ymax(dumped.part)
        )
),

-- An area a line meets whose cut raised, or one of whose pieces could not be
-- measured against its edge.
uncut as (
    select notice_id
    from touching
    where inside is null
    union distinct
    select notice_id
    from parts
    where along_edge is null
),

stretches as (
    select
        notice_id,
        st_collect(list(part order by line_id, part_path)) as geom
    from parts
    where not along_edge
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
        areas.area_geojson,
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
    end as shade_geojson,
    area_geojson
from verdicts
where
    stretches > 0
    or (shade is not null and not st_isempty(shade) and st_dimension(shade) = 2)
