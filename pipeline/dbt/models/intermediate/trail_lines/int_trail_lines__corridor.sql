{{ config(materialized='table') }}
-- The A.T.'s corridor, lib/corridor.build_corridor(): every centerline
-- segment buffered by 30 miles in EPSG:5070 metres, unioned, and taken back to
-- lon/lat, always_xy on both legs (that module's docstring says what dropping
-- it did). One row. export_trails.py keeps a line that touches it (TL14), and
-- export_poi.py clips points to the same polygon.
--
-- The widening for other organizations' lines (build_corridor's
-- `network_path`) is a join on the network's lines, not part of this
-- polygon, since #1311 — The vector build went from 20 to 108 minutes in
-- twelve days: a corridor union over 466k lines paid twice, every external
-- layer re-fetched every run, and a publish that pays a round-trip per
-- object. export_trails.py never asks for it.
with segments as (
    select geom from {{ ref('stg_atc__centerline_segments') }}
)

select
    'centerline' as source_key,
    st_transform(
        st_union_agg(
            st_buffer(
                st_transform(
                    geom, 'EPSG:4326', 'EPSG:5070', always_xy := true
                ),
                -- Python's `buffer_miles * METERS_PER_MILE`, the same two
                -- doubles multiplied: 48280.32 m.
                cast({{ var('trail_lines_corridor_buffer_miles') }} as double)
                * cast({{ var('mile_axis_metres_per_mile') }} as double)
            )
        ),
        'EPSG:5070',
        'EPSG:4326',
        always_xy := true
    ) as geom
from segments
