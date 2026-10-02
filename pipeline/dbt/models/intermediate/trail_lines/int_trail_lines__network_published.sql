-- placeholder: tl-net replaces this file
--
-- The network half of the trail_lines mart: one row per line
-- nearby_trails.geojson publishes, in exactly the mart's columns
-- (marts/trail_lines/_trail_lines__models.yml says what each holds). This
-- stand-in has the columns and no rows, so the mart and its contract build
-- before the network half lands. tl-net's model of the same name replaces
-- it, and _trail_lines__placeholders.yml, which documents it, goes with it.
--
-- It reads stg_registry__sources only so that it is not a root model, which
-- the project evaluator refuses. Not int_sources__publication, which the
-- mart reads directly: the evaluator reads a single-use model between a
-- parent and its child as an upstream concept rejoined.
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
from {{ ref('stg_registry__sources') }}
where false
