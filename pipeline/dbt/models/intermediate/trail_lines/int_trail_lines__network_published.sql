{{ config(materialized='table') }}
{%- set decimals = var('trail_lines_network_coordinate_decimals') %}
-- The network's half of the trail_lines mart: one row per network line that
-- ships, in the mart's 23 columns, by name and type (tl-at's contract,
-- models/marts/trail_lines/_trail_lines__models.yml). The mart unions it
-- with the A.T.'s half. closure_reason and closure_source are set only on a
-- section inside one of NYS Parks' closed areas
-- (int_trail_lines__network_area_closures).
--
-- THE GEOMETRY IS THE ONE A PHONE DRAWS, as the mart's contract has it: the
-- 1 m line from int_trail_lines__network_navigation, every vertex cut to six
-- decimals (TL23, NEARBY_COORDINATE_DECIMALS) as Python's round() cuts it.
-- That is not DuckDB's round(): measured 2026-10-02 on 266,800 doubles built
-- to sit on, or an ulp either side of, a half at 6, 3 and 2 decimals,
-- round(x, n) answered differently from Python on 14,125 and
-- cast(printf('%.nf', x) as double) on none, at all three. A line the cut
-- would leave with a part of fewer than two distinct vertices keeps every
-- vertex uncut (_rounded_geometry()'s never-degenerate rule). `geom_geojson`
-- is the GeoJSON geometry object nearby_trails.geojson carries, as text,
-- `type` first.
--
-- TWO LENGTHS, both in metres on the WGS84 ellipsoid: `length_m` on the line
-- as its steward published it, before any simplification (decision 8:
-- Douglas-Peucker only shortens a line, so a length taken after it
-- under-reports a day hike), and `published_length_m` on the 1 m line before
-- the cut, which is what records_to_geojson()'s `length_miles` is rounded
-- from. Each is macros/geodesic_length_m.sql's (decision 97, the
-- maintainer's poll of 2026-10-06, as decision 90 measures the graph's
-- edges), handed the line projected to EPSG:5070 as the macro takes it. The
-- trip there and back changed no line's length by more than 7.3e-7 m against
-- the lon/lat line's own (measured 2026-10-06 on UA's 329,446 routable
-- lines, with the macro's ST_Length_Spheroid). They were EPSG:5070 metres
-- until then, which read five miles due north as 4.44 at Anchorage and 5.04
-- at Harriman. export_nearby_trails._geodesic_miles_all measures the same
-- length with pyproj, and tests/test_dbt_trail_lines_network_parity.py holds
-- the two to a micrometre.
--
-- `feature_order` is the line's place in nearby_trails.geojson: sources in
-- the registry's order, as main() runs them, then by id. The Python's order
-- within a layer is the fetched file's, which the warehouse does not land.
--
-- The A.T.'s columns are null on every network row: `vertex_miles` and
-- `monotonic_breaks` (the calibrated mile axis, TL22) and the four spur_
-- fields (spurs.json's).
with navigation as (
    select * from {{ ref('int_trail_lines__network_navigation') }}
),

lines as (
    select
        *,
        st_geomfromtext(geom_wkt) as geom,
        st_geometrytype(st_geomfromtext(geom_wkt)) = 'MULTILINESTRING'
            as is_multi
    from navigation
),

-- Every line as a list of parts, each a list of [longitude, latitude] at
-- full precision: a LineString is one part.
parts as (
    select
        *,
        case
            when is_multi
                then cast(
                    json_extract(st_asgeojson(geom), '$.coordinates')
                    as double[][][]
                )
            else [
                cast(
                    json_extract(st_asgeojson(geom), '$.coordinates')
                    as double[][]
                )
            ]
        end as full_parts
    from lines
),

rounded as (
    select
        *,
        list_transform(
            full_parts,
            lambda part: list_transform(
                part,
                lambda point: list_transform(
                    point,
                    lambda coordinate: cast(
                        printf('%.{{ decimals }}f', coordinate) as double
                    )
                )
            )
        ) as cut_parts
    from parts
),

chosen as (
    select
        *,
        case
            when
                list_bool_and(
                    list_transform(
                        cut_parts, lambda part: len(list_distinct(part)) >= 2
                    )
                )
                then cut_parts
            else full_parts
        end as chosen_parts
    from rounded
)

select
    trail_line_id,
    club,
    source_key,
    _loaded_at,
    'network' as line_kind,
    row_number() over (order by file_row, trail_line_id) - 1 as feature_order,
    name,
    blaze_color,
    trail_status,
    trail_status_basis,
    closure_kind,
    closure_reason,
    closure_source,
    duplicate_of,
    cast(
        json_object(
            'type',
            case when is_multi then 'MultiLineString' else 'LineString' end,
            'coordinates',
            case
                when is_multi then to_json(chosen_parts)
                else to_json(list_extract(chosen_parts, 1))
            end
        ) as varchar
    ) as geom_geojson,
    {{ geodesic_length_m(
        "st_transform(st_geomfromtext(full_resolution_wkt), 'EPSG:4326', 'EPSG:5070', always_xy := true)"
    ) }} as length_m,
    {{ geodesic_length_m(
        "st_transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true)"
    ) }} as published_length_m,
    cast(null as double[]) as vertex_miles,
    cast(null as integer) as monotonic_breaks,
    cast(null as double) as spur_length_ft,
    cast(null as varchar) as spur_destination_poi_id,
    cast(null as integer) as spur_destination_distance_m,
    cast(null as double) as spur_junction_mile
from chosen
