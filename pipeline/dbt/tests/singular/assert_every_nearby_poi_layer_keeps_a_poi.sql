-- export_nearby_poi.py's completeness gate (fail_if_incomplete over
-- count_problems): every layer nearby_poi.geojson reads must keep at least
-- one POI, counted before any ring clips it, because the gate exists to
-- catch a source that silently returned zero (an ArcGIS schema change, a
-- renamed asset value) and the ring legitimately removes most of some
-- layers. Counted from the poi_sources seed rather than from the rows, so a
-- layer that vanished entirely counts 0. Fails by returning each empty
-- layer.
with layers as (
    select source_key from {{ ref('poi_sources') }}
    where phone_files = 'nearby_poi'
),

kept as (
    select
        source_key,
        count(*) as pois
    from {{ ref('int_points_of_interest__publishable') }}
    where phone_files = 'nearby_poi'
    group by source_key
)

select
    layers.source_key,
    coalesce(kept.pois, 0) as pois
from layers
left join kept on layers.source_key = kept.source_key
where coalesce(kept.pois, 0) < 1
