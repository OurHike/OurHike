{{ config(materialized='table') }}
-- The A.T.'s one mile axis: each centerline piece oriented and scaled by
-- ATC's own half-mile markers, in mile order, in EPSG:5070 metres. The SQL
-- form of export_elevation.calibrated_trail_axis (#652, #753), which every
-- published A.T. mile comes off today: a POI's `mile`
-- (export_poi.attach_miles), a spur's `junction_mile`
-- (export_spurs.attach_junction_miles), every vertex's mile in
-- trail_miles.json (export_trails.vertex_miles) and the profile's
-- `distance_mi` (export_elevation.build_profile). One row per piece.
--
-- The rule is in the three models before this one, each held to the Python
-- by a unit test: int_trail_lines__mile_axis_pieces (merge and straight-axis
-- order), int_trail_lines__mile_axis_markers (the snap) and
-- int_trail_lines__mile_axis_calibration (orientation, scale and mile
-- order). This model only makes the calibrated piece's WKT into geometry and
-- its calibration_json into doubles and lists. It has no unit test of its
-- own because dbt 2.0.6 cannot hold a GEOMETRY, list or DOUBLE column to
-- the bit in one (int_trail_lines__mile_axis_calibration says what it does
-- instead); its data test holds length_m to the geometry.
--
-- HOW A CONSUMER READS A MILE OFF IT, which is how each of the four
-- exporters does today:
-- 1. the point in EPSG:5070: st_transform(point, 'EPSG:4326', 'EPSG:5070',
--    always_xy := true);
-- 2. its nearest piece: the least st_distance(geom_5070, point), a tie to the
--    lower piece_id (shapely's STRtree breaks one by its own visiting order,
--    which its docstring calls possibly nondeterministic);
-- 3. the along-distance in miles: st_linelocatepoint(geom_5070, point) *
--    length_m / 1609.344, as its own column;
-- 4. the mile: mile_at_along('<that column>', 'anchor_along_mi',
--    'anchor_mile'), rounded to three decimals where it is published.
select
    piece_id,
    pre_calibration_order,
    st_geomfromtext(geom_5070_wkt) as geom_5070,
    cast(json_extract(calibration_json, '$.length_m') as double) as length_m,
    cast(json_extract(calibration_json, '$.start_mile') as double)
        as start_mile,
    cast(json_extract(calibration_json, '$.end_mile') as double) as end_mile,
    cast(json_extract(calibration_json, '$.anchor_along_mi') as double[])
        as anchor_along_mi,
    cast(json_extract(calibration_json, '$.anchor_mile') as double[])
        as anchor_mile,
    anchor_count,
    snapped_marker_count,
    reversed_by_markers
from {{ ref('int_trail_lines__mile_axis_calibration') }}
