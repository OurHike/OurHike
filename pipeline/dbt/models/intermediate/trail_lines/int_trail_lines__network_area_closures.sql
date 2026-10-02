{{ config(materialized='table') }}
-- Every network line, split against NYS Parks' temporary closed areas
-- (export_nearby_trails.py's apply_area_closures(), #964): the part inside a
-- closed area ships closed and the part outside ships open, so
-- nearby_trails.geojson carries the barred band exactly where the ground is
-- closed. Read between int_trail_lines__network_deduplicated and the 1 m
-- pass, where main() applies it: after the dedupe, so a junior is judged
-- against the line its steward published, and before simplify_records(),
-- which makes the geometry final.
--
-- WHY THIS IS STILL HERE (decision 44): #1152 — Move OPRHP's temporary
-- closures onto the conditions clock, where a safety layer belongs — is to
-- publish the areas on the hourly conditions files, and the closures mart
-- already carries them (int_closures__oprhp_areas). But a phone in the field
-- draws the tape from this file's `trail_status`, and no deployed build
-- reads a conditions file for areas, so v1 of nearby_trails.geojson keeps
-- the split: expand, then contract, retiring it only once a release that
-- reads the conditions file has shipped.
--
-- THE RULE, apply_area_closures()' own, on the line as its steward published
-- it, in longitude and latitude, with the same GEOS operations shapely runs:
-- - the areas' union, unary_union() in the layer's order; a line that does
--   not intersect it ships unchanged;
-- - `inside` is the line's intersection with the union and `outside` its
--   difference, each reduced to the LineStrings of two or more distinct
--   vertices it contains (_line_parts(): a point where a trail only grazes a
--   corner is not a walkable section). A line with nothing inside ships
--   unchanged: it touches a boundary and goes no further in;
-- - the inside part ships closed, closure_kind 'area', with the reason of
--   the area it overlaps most (planar length in degrees, as shapely
--   measures it), a tie going to the area first in the layer, and
--   closure_source the closure layer's own registry key (#1142: the sheet
--   speaks the closing organization's name, not the line's);
-- - where both parts exist the closed one's id gains `:closed` and the open
--   one's `:open`, so no two features share an id; the open part keeps every
--   property of its line. A part of several pieces stays a MultiLineString
--   (_merge()), never merged across the gap the closure made.
-- Measured 2026-10-02 against shapely 2.1.2 (GEOS 3.13.1), on DuckDB 1.5.4
-- with spatial 28db190 (the engine dbt 2.0.6 runs) and again on 1.5.5:
-- ST_Intersection and ST_Difference gave the same pieces, vertex for vertex,
-- on 1,522 of 1,522 random lines touching a union of 4 areas; ST_Union_Agg in
-- the layer's order gave unary_union()'s WKT exactly on 200 of 200 unions;
-- and the split did not depend on the areas' order on 3,000 lines across all
-- 24 orders of 4 overlapping areas, so the order matters only for the tie.
--
-- NO DATE IS INVENTED: OPRHP publishes none per feature ("Closed Until 2027"
-- is prose inside the reason), so a closed part carries the reason verbatim
-- and nothing else. An empty closures layer is a good week, not a failure,
-- and then every line ships unchanged.
--
-- THE AREAS ARE OPRHP'S because int_closures__oprhp_areas is: the registry
-- marks one closure-area layer today, and
-- assert_every_closure_area_layer_is_applied_to_the_network stops the build
-- when it marks another this model does not read.
with lines as (
    select
        *,
        st_geomfromtext(geom_wkt) as geom
    from {{ ref('int_trail_lines__network_deduplicated') }}
),

areas as (
    select
        source_row,
        closure_reason,
        st_geomfromgeojson(geom_geojson) as geom
    from {{ ref('int_closures__oprhp_areas') }}
),

-- No row at all in a week with nothing closed, rather than the empty
-- GEOMETRYCOLLECTION ST_Union_Agg makes of no rows: dbt 2.0.6's DuckDB
-- (1.5.4, spatial 28db190) crashes with a segmentation fault on
-- ST_Intersects of every line against an empty collection (measured
-- 2026-10-02 on the fixture's 66 lines; DuckDB 1.5.5 answers false), so an
-- empty layer must never reach that call.
closed_ground as (
    select st_union_agg(geom order by source_row) as geom
    from areas
    having count(*) > 0
),

touched as (
    select
        lines.*,
        st_intersection(lines.geom, closed_ground.geom) as inside_geom,
        st_difference(lines.geom, closed_ground.geom) as outside_geom
    from lines
    cross join closed_ground
    where st_intersects(lines.geom, closed_ground.geom)
),

-- _line_parts(): each atomic piece, depth first as shapely walks them, kept
-- when it is a LineString of two or more distinct vertices, which is exactly
-- when its bounding box has a width or a height.
parted as (
    select
        *,
        list_filter(
            list_transform(
                st_dump(inside_geom),
                lambda piece: struct_extract(piece, 'geom')
            ),
            lambda part: st_geometrytype(part) = 'LINESTRING'
            and (
                st_xmin(part) < st_xmax(part)
                or st_ymin(part) < st_ymax(part)
            )
        ) as inside_parts,
        list_filter(
            list_transform(
                st_dump(outside_geom),
                lambda piece: struct_extract(piece, 'geom')
            ),
            lambda part: st_geometrytype(part) = 'LINESTRING'
            and (
                st_xmin(part) < st_xmax(part)
                or st_ymin(part) < st_ymax(part)
            )
        ) as outside_parts
    from touched
),

split_lines as (
    select *
    from parted
    where len(inside_parts) > 0
),

-- The area each closed part is described by: the one the whole line
-- overlaps most, a tie to the first in the layer (max()'s first maximum).
reasons as (
    select
        split_lines.trail_segment_key,
        areas.closure_reason
    from split_lines
    cross join areas
    qualify
        row_number() over (
            partition by split_lines.trail_segment_key
            order by
                st_length(st_intersection(split_lines.geom, areas.geom)) desc,
                areas.source_row asc
        ) = 1
),

closed_parts as (
    select
        split_lines.trail_segment_key || ':closed' as trail_segment_key,
        split_lines.source_key,
        split_lines.club,
        split_lines.file_row,
        case
            when len(split_lines.outside_parts) > 0
                then split_lines.trail_line_id || ':closed'
            else split_lines.trail_line_id
        end as trail_line_id,
        split_lines.name,
        'closed' as trail_status,
        'closed_area' as trail_status_basis,
        'area' as closure_kind,
        reasons.closure_reason,
        'oprhp_trail_closures' as closure_source,
        split_lines.blaze_color,
        split_lines.duplicate_of,
        st_astext(
            case
                when len(split_lines.inside_parts) = 1
                    then list_extract(split_lines.inside_parts, 1)
                else st_collect(split_lines.inside_parts)
            end
        ) as geom_wkt,
        split_lines._loaded_at
    from split_lines
    inner join reasons
        on split_lines.trail_segment_key = reasons.trail_segment_key
),

open_parts as (
    select
        trail_segment_key || ':open' as trail_segment_key,
        source_key,
        club,
        file_row,
        trail_line_id || ':open' as trail_line_id,
        name,
        trail_status,
        trail_status_basis,
        closure_kind,
        cast(null as varchar) as closure_reason,
        cast(null as varchar) as closure_source,
        blaze_color,
        duplicate_of,
        st_astext(
            case
                when len(outside_parts) = 1
                    then list_extract(outside_parts, 1)
                else st_collect(outside_parts)
            end
        ) as geom_wkt,
        _loaded_at
    from split_lines
    where len(outside_parts) > 0
),

unsplit as (
    select
        lines.trail_segment_key,
        lines.source_key,
        lines.club,
        lines.file_row,
        lines.trail_line_id,
        lines.name,
        lines.trail_status,
        lines.trail_status_basis,
        lines.closure_kind,
        cast(null as varchar) as closure_reason,
        cast(null as varchar) as closure_source,
        lines.blaze_color,
        lines.duplicate_of,
        lines.geom_wkt,
        lines._loaded_at
    from lines
    left join split_lines
        on lines.trail_segment_key = split_lines.trail_segment_key
    where split_lines.trail_segment_key is null
)

select * from unsplit
union all
select * from closed_parts
union all
select * from open_parts
