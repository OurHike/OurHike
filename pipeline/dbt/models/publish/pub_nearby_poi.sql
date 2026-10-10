{{ config(format='json', location='nearby_poi.geojson') }}
-- nearby_poi.geojson: the other organizations' POIs (NYS DEC, NYS Parks,
-- USFS, NYC Parks), one FeatureCollection of mixed types, in the shape
-- export_nearby_poi.py's records_to_geojson() writes with json.dumps: a
-- property that is null is left out rather than written null, so `name` is
-- absent on an unnamed POI and there is no `mile` at all; the id is
-- `{source key}:{the layer's id}`, and `source_feature_id` keeps the type
-- the layer wrote (OBJECTID is a number). Every coordinate is the double
-- itself, as json.dumps prints it. Features in the order the Python reads
-- its layers and rows. NYNJTC's Long Path guide's waypoints come last, as
-- guide_records() appends them, with the guide's own fields: lp_section,
-- section_mile, placement, source_url, and position_error_m,
-- off_trail_miles and water_reliability where the record has them. A
-- plumbed tap or fountain whose layer records no shutoff season carries
-- `water_caution` 'no_shutoff_season' (decision 65), which the waypoint card
-- reads; no other POI carries the member at all.
with pois as (
    select * from {{ ref('points_of_interest', v=1) }}
    where phone_files = 'nearby_poi'
)

select
    'FeatureCollection' as type,
    coalesce(
        list(
            json_object(
                'type', 'Feature',
                'geometry', cast(geom_geojson as json),
                -- A merge patch drops every member whose value is null.
                'properties', json_merge_patch(
                    '{}',
                    json_object(
                        'id', poi_id,
                        'poi_type', poi_type,
                        'trail_id', trail_id,
                        'source', source,
                        'source_feature_id', source_feature_id_json,
                        'name', name,
                        'lat', lat,
                        'lon', lon,
                        'confidence', confidence,
                        'description', description,
                        'lp_section', lp_section,
                        'section_mile', section_mile,
                        'placement', placement,
                        'source_url', source_url,
                        'position_error_m', position_error_m,
                        'off_trail_miles', off_trail_miles,
                        'water_reliability', water_reliability,
                        'water_caution', water_caution,
                        'site_id', site_id,
                        'site_role', site_role,
                        'site_name', site_name,
                        'trails_closed_within_m', trails_closed_within_m
                    )
                )
            )
            order by record_order
        ),
        []
    ) as features
from pois
