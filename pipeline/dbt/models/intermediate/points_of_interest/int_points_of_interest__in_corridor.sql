{{ config(materialized='table') }}
{%- set ring_m =
    "cast(" ~ var('poi_network_ring_feet') ~ " as double) * "
    ~ var('poi_metres_per_foot') %}
{%- set whole_part_max = var('poi_network_ring_part_max_vertices') %}
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
-- A LONG LINE IS ASKED SEGMENT BY SEGMENT, which gives the same answer and
-- is what keeps this model inside a runner's memory. A part of a line with
-- more than var `poi_network_ring_part_max_vertices` (1,024) vertices is
-- probed as its segments, each a two-vertex line on the part's own
-- coordinates; a shorter part is probed whole. A disc meets a line exactly
-- when it meets one of the line's segments, so the set of points kept does
-- not move; the 500 ft disc is still a 32-sided ST_Buffer, never a distance.
--
-- Why: asking whole lines failed on the live warehouse in
-- refresh-reference.yml run 37132427696 (2026-10-03), "Out of Memory Error:
-- failed to allocate data of size 16.0 MiB (12.4 GiB/12.4 GiB used)".
-- Measured 2026-10-03 against UA's published network (release 2026-10-03-2:
-- 329,446 lines, 17,228,035 vertices) and 47,665 points with real or
-- jittered real positions, through dbt 2.0.6 (its DuckDB 1.5.4, spatial
-- 28db190) under memory_limit 8GB: whole lines failed the same way (7.4
-- GiB of 7.4 GiB used) after 85 s; segments built this model in 23 s at a
-- 2.39 GiB peak, with the same 42,577 rows, by md5 of their keys, as the
-- whole-line SQL on DuckDB 1.5.5 (Python's, which builds it at 1.73 GiB in
-- 224 s: why lib/corridor.py never met this). Three lines cause it: the
-- Continental Divide Trail's two longest MultiLineStrings (704,095 and
-- 402,563 vertices) and the Pacific Crest Trail (265,802, one LineString),
-- whose bounding boxes 13,801 discs fall inside. On 1.5.4 the spatial join
-- holds each candidate line's memory per pair it tests (Reasoned from one
-- measurement: 3,000 discs against the Pacific Crest Trail alone exhausted
-- 8 GB in the join and peaked at 0.35 GiB as a plain ST_Intersects). Whole
-- lines failed whichever side the join built its R-tree on, and with a
-- persisted R-tree index on a lines table, which the plan did not use.
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
    -- No centerline is no corridor row, never an empty one: on dbt 2.0.6's
    -- DuckDB 1.5.4, ST_Intersects against the GEOMETRYCOLLECTION EMPTY a
    -- union over zero rows gives kills the process (the dbt skill's traps).
    having count(*) > 0
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
    select count(*) > 0 as has_lines
    from {{ ref('int_trail_lines__network_published') }}
),

network_parts as (
    -- Each LineString, and each part of a MultiLineString, on its own row.
    select
        struct_extract(part, 'geom') as part_5070,
        st_npoints(struct_extract(part, 'geom')) as vertex_count
    from (
        select unnest(st_dump(geom_5070)) as part from network_lines
    ) as dumped
),

network_segments as (
    -- A long part's segments: vertex i to vertex i + 1, for every i, on the
    -- vertices ST_Points gives, which keeps a repeated vertex.
    select st_makeline(segment_start, segment_end) as piece_5070
    from (
        select
            unnest(list_slice(vertices, 1, -2)) as segment_start,
            unnest(list_slice(vertices, 2, -1)) as segment_end
        from (
            select
                list_transform(
                    st_dump(st_points(part_5070)),
                    lambda vertex: struct_extract(vertex, 'geom')
                ) as vertices
            from network_parts
            where vertex_count > {{ whole_part_max }}
        ) as long_parts
    ) as pairs
),

network_pieces as (
    select part_5070 as piece_5070
    from network_parts
    where vertex_count <= {{ whole_part_max }}
    union all
    select piece_5070 from network_segments
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
    -- Only what the three joins read; every other column comes back from
    -- `publishable` by poi_key.
    select
        poi_key,
        lon,
        lat,
        boundary_source,
        st_transform(
            st_point(lon, lat), 'EPSG:4326', 'EPSG:5070', always_xy := true
        ) as point_5070
    from publishable
),

corridor_hits as (
    -- keep_within_corridor(): the point intersects the corridor polygon.
    select distinct points.poi_key
    from points
    inner join corridor
        on st_intersects(st_point(points.lon, points.lat), corridor.geom)
),

ring_hits as (
    -- near_network_sql(): the point buffered by the ring, and any published
    -- line the disc intersects, asked of the line's pieces.
    select distinct points.poi_key
    from points
    inner join network_pieces
        on st_intersects(
            network_pieces.piece_5070,
            st_buffer(points.point_5070, {{ ring_m }})
        )
),

boundary_hits as (
    -- inside_boundary_sql(): ST_Covers, so a point on the boundary line is
    -- inside.
    select distinct points.poi_key
    from points
    inner join boundaries
        on
            points.boundary_source = boundaries.boundary_source
            and st_covers(boundaries.geom_5070, points.point_5070)
),

judged as (
    select
        publishable.*,
        corridor_hits.poi_key is not null as in_at_corridor,
        ring_hits.poi_key is not null as near_network,
        boundary_hits.poi_key is not null as inside_boundary
    from publishable
    left join corridor_hits on publishable.poi_key = corridor_hits.poi_key
    left join ring_hits on publishable.poi_key = ring_hits.poi_key
    left join boundary_hits on publishable.poi_key = boundary_hits.poi_key
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
    judged._loaded_at
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
