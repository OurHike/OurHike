{{ config(materialized='table') }}
-- The publishable POIs inside the ground their file covers (PO05, PO33).
--
-- THE A.T. FAMILY keeps only what lib/corridor.py's corridor reaches: the
-- union of a 30-mile buffer around every A.T. centerline segment, buffered
-- in EPSG:5070 metres and turned back to lon/lat with always_xy on both legs,
-- with a point kept where it intersects that polygon. These are
-- build_corridor()'s and keep_within_corridor()'s functions in the same
-- order on the same rows, and the buffer distance is var
-- `poi_corridor_buffer_miles` (lib/corridor.py's BUFFER_MILES) times
-- METERS_PER_MILE, as two doubles, which is the double the Python's own
-- product prints as.
--
-- NOT HERE YET: the network ring. Since #1016 and #1311 the corridor also
-- reaches any point within NETWORK_BUFFER_FEET (500 ft) of another
-- organization's published line, read from nearby_trails.geojson. Those
-- lines are the trail_lines family's to publish, and no model holds them
-- yet, so this is the A.T.'s thirty miles alone: what export_poi.py itself
-- does on a run with no nearby_trails.geojson, and on today's sources no
-- difference, because every A.T.-family layer but OSM water sits on A.T.
-- ground (lib/corridor.py's NETWORK_BUFFER_FEET comment), and OSM water is
-- not landed yet (#1652). It lands with the network lines.
--
-- THE OTHER ORGANIZATIONS' POIs pass untouched: export_nearby_poi.py has no
-- extent of its own (the maintainer's "Don't limit data from orgs based on
-- geography", #1019). Its 500 ft ring around the published network lines
-- (clip_to_network, PO05's other half) waits on the same lines, and until
-- they exist it admits every row, as clip_to_network does when the network
-- artifact holds none.
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
)

select
    publishable.*,
    -- PO10, mark_off_trail_records(): the other organization's trail an
    -- A.T.-family point sits on, which withholds its A.T. mile. Only OSM water
    -- is ever marked, and no staging model lands OSM water yet (#1652), so no
    -- row here is: null on every row, until OSM water lands with its reach
    -- verdicts' `nearest_source`.
    cast(null as varchar) as not_on_at
from publishable
where
    publishable.phone_files = 'nearby_poi'
    or exists (
        select 1 from corridor
        where
            st_intersects(
                st_point(publishable.lon, publishable.lat), corridor.geom
            )
    )
