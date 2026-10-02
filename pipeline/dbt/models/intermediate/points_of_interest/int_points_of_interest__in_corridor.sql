{{ config(materialized='table') }}
{%- set ring_m =
    "cast(" ~ var('poi_network_ring_feet') ~ " as double) * "
    ~ var('poi_metres_per_foot') %}
-- The publishable POIs inside the ground their file covers (PO05, PO33).
--
-- THE A.T. FAMILY keeps what lib/corridor.py's corridor reaches
-- (build_corridor() and keep_within_corridor(), in that order on the same
-- rows): a point inside the union of a 30-mile buffer around every A.T.
-- centerline segment, buffered in EPSG:5070 metres and turned back to
-- lon/lat with always_xy on both legs; or, since #1016 and #1311 — The
-- vector build went from 20 to 108 minutes in twelve days: a corridor union
-- over 466k lines paid twice, every external layer re-fetched every run, and
-- a publish that pays a round-trip per object, a point within
-- NETWORK_BUFFER_FEET (500 ft) of a published network line. The buffer
-- distance is var `poi_corridor_buffer_miles` times METERS_PER_MILE, as two
-- doubles, which is the double the Python's own product prints as.
--
-- THE OTHER ORGANIZATIONS' POIs have no extent of their own (#1019 — A
-- survey's proposed ring decides which of NYS Parks' and NYNJTC's trails ship,
-- and DEC's ship not at all). export_nearby_poi.py's clip_to_network() keeps
-- an amenity within the same 500 ft of a published line, every parking area
-- and trailhead whatever its distance (NETWORK_RING_EXEMPT_TYPES), and, as an
-- OR, a point inside a park boundary its layer names in sources.json's
-- `boundary_source` (ST_Covers, so a point on the boundary line is inside).
--
-- THE RING IS lib/corridor.py's near_network_sql(): the point buffered by
-- the ring in EPSG:5070 metres and every line the disc intersects, so the
-- question is asked the way the Python asks it. The lines are the published
-- network, int_trail_lines__network_published (the trail_lines family's,
-- the lines nearby_trails.geojson carries, as phones draw them), which is
-- what both exporters read the network artifact for.
--
-- NOT CLIPPING IS THE FAILURE DIRECTION: with no published network line at
-- all (the licence gate holding every steward's lines back is an ordinary
-- state), no ring applies and every row the ring would judge is kept, as
-- clip_to_network() returns every record when the artifact holds none. A
-- boundary layer that is absent admits nobody. The one boundary layer any
-- POI source names today is nyc_park_polygons (both NYC Parks layers); a new
-- `boundary_source` admits nothing until its layer is added below, which is
-- the direction the Python's boundary_paths_for() takes with a name it
-- cannot find.
with publishable as (
    select * from {{ ref('int_points_of_interest__publishable') }}
),

centerline as (
    select geom from {{ ref('stg_atc__centerline_segments') }}
    where geom is not null
),

corridor as (
    select
        st_transform(
            st_union_agg(
                st_buffer(
                    st_transform(
                        geom, 'EPSG:4326', 'EPSG:5070', always_xy := true
                    ),
                    cast({{ var('poi_corridor_buffer_miles') }} as double)
                    * {{ var('mile_axis_metres_per_mile') }}
                )
            ),
            'EPSG:5070', 'EPSG:4326', always_xy := true
        ) as geom
    from centerline
),

network_lines as (
    -- lib/corridor.py's load_network_lines(): every published line, in
    -- EPSG:5070 metres.
    select
        st_transform(
            st_geomfromgeojson(geom_geojson),
            'EPSG:4326',
            'EPSG:5070',
            always_xy := true
        ) as geom_5070
    from {{ ref('int_trail_lines__network_published') }}
),

network_state as (
    select count(*) > 0 as has_lines from network_lines
),

boundaries as (
    -- lib/corridor.py's load_boundary_polygons(), per boundary layer.
    select
        'nyc_park_polygons' as boundary_source,
        st_transform(geom, 'EPSG:4326', 'EPSG:5070', always_xy := true)
            as geom_5070
    from {{ ref('base_nycparks__nyc_park_polygons') }}
    where geom is not null
),

points as (
    select
        publishable.*,
        st_transform(
            st_point(publishable.lon, publishable.lat),
            'EPSG:4326',
            'EPSG:5070',
            always_xy := true
        ) as point_5070
    from publishable
),

judged as (
    select
        points.*,
        exists(
            select 1 from corridor
            where st_intersects(st_point(points.lon, points.lat), corridor.geom)
        ) as in_at_corridor,
        exists(
            select 1 from network_lines
            where
                st_intersects(
                    network_lines.geom_5070,
                    st_buffer(points.point_5070, {{ ring_m }})
                )
        ) as near_network,
        exists(
            select 1 from boundaries
            where
                boundaries.boundary_source = points.boundary_source
                and st_covers(boundaries.geom_5070, points.point_5070)
        ) as inside_boundary
    from points
)

select
    judged.poi_key,
    judged.source_key,
    judged.file_order,
    judged.source_row,
    judged.club,
    judged.source,
    judged.phone_files,
    judged.trail_id,
    judged.source_feature_id,
    judged.source_feature_id_json,
    judged.derived_id,
    judged.name,
    judged.poi_type,
    judged.confidence,
    judged.confidence_floor,
    judged.asset,
    judged.facility,
    judged.lon,
    judged.lat,
    judged.properties,
    judged._loaded_at,
    -- PO10, mark_off_trail_records(): the other organization's trail an
    -- A.T.-family point sits on, which withholds its A.T. mile. Only OSM water
    -- is ever marked, and no staging model lands OSM water yet, so no row here
    -- is: null on every row, until OSM water lands with its reach verdicts'
    -- `nearest_source`.
    cast(null as varchar) as not_on_at
from judged
cross join network_state
where
    case
        when judged.phone_files = 'poi_by_type'
            then judged.in_at_corridor or judged.near_network
        else
            list_contains(
                {{ var('poi_network_ring_exempt_types') }}, judged.poi_type
            )
            or not network_state.has_lines
            or judged.near_network
            or judged.inside_boundary
    end
