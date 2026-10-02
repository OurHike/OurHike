{{ config(format='json', location='network_overview.geojson') }}
-- network_overview.geojson, the sketch of every other organization's trails
-- the opening camera draws (#1135, client/src/lib/config.ts's
-- NETWORK_OVERVIEW_KEY), in the shape export_nearby_trails.py's
-- write_overview() writes (decision 44's v1): one MultiLineString Feature
-- per int_trail_lines__network_overview_features row, in its order.
--
-- Through int_trail_lines__network_overview_seam, the sketch is simplified
-- from the 1 m line at full precision, which is what write_overview() is
-- handed. Not the trail_lines mart's six-decimal geometry: parity holds the
-- sketch to the Python, which never sees the cut.
with overview_features as (
    select * from {{ ref('int_trail_lines__network_overview_features') }}
),

features as (
    select
        feature_order,
        json_object(
            'type', 'Feature',
            'properties', cast(properties_json as json),
            'geometry', json_object(
                'type', 'MultiLineString',
                'coordinates', cast(coordinates_json as json)
            )
        ) as feature
    from overview_features
)

select
    -- Quoted because `type` is a keyword to SQLFluff's RF04, and GeoJSON names
    -- the member so; quoting it is what RF06 calls unnecessary.
    'FeatureCollection' as "type",  -- noqa: RF06
    coalesce(list(feature order by feature_order), []) as features
from features
