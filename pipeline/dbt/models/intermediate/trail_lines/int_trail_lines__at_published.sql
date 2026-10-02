-- placeholder: tl-at fills this file next
--
-- The A.T. half of the trail_lines mart: one row per line trails.geojson
-- publishes (the centerline's chains, side trails and spurs), in exactly the
-- mart's columns (marts/trail_lines/_trail_lines__models.yml). It has the
-- columns and no rows for now, so the mart's contract can be committed, and
-- tl-net can build against it, before the A.T.'s intermediates land.
select
    cast(null as varchar) as trail_line_id,
    cast(null as varchar) as club,
    cast(null as varchar) as source_key,
    cast(null as timestamptz) as _loaded_at,
    cast(null as varchar) as line_kind,
    cast(null as bigint) as feature_order,
    cast(null as varchar) as name,
    cast(null as varchar) as blaze_color,
    cast(null as varchar) as trail_status,
    cast(null as varchar) as trail_status_basis,
    cast(null as varchar) as closure_kind,
    cast(null as varchar) as duplicate_of,
    cast(null as varchar) as geom_geojson,
    cast(null as double) as length_m,
    cast(null as double) as published_length_m,
    cast(null as double[]) as vertex_miles,
    cast(null as integer) as monotonic_breaks,
    cast(null as double) as spur_length_ft,
    cast(null as varchar) as spur_destination_poi_id,
    cast(null as integer) as spur_destination_distance_m,
    cast(null as double) as spur_junction_mile
from {{ ref('stg_atc__centerline_segments') }}
where false
