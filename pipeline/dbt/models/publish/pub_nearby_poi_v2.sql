{{ config(format='json', location='nearby_poi_v2.geojson') }}
-- v2/nearby_poi.geojson (decision 44's v2 of the points_of_interest mart):
-- the other organizations' POIs as v1's nearby_poi.geojson carries them, in
-- the same order, with each position held once, as the point's coordinates
-- at 6 decimals, and no `lat` and `lon` properties (stage 6 of #1793;
-- pipeline/ELT.md, "Making the download smaller"). Every other property is
-- v1's (pub_nearby_poi.sql), left out where it is null as v1 leaves it out.
-- NYNJTC's Long Path guide's waypoints come last with the guide's own
-- fields, lp_section to water_reliability, as v1's do.
-- parity.py's nearby_poi_v2 family holds each feature to v1's, its
-- coordinates to Python's round(x, 6) of v1's lat and lon.
--
-- `source_feature_id` stays: ELT.md lets it go from this file only once no
-- pipeline reader needs it, and nobody has checked that yet.
--
-- WHICH POIs, unchanged from v1: every other organization's POI is still
-- here, water and shelters and everything else. Moving their non-water,
-- non-shelter rows to 1° cells is decision 9's tier (b), which changes what
-- a phone with no signal holds, and is the maintainer's to decide (ELT.md's
-- open question on trailheads and parking).
with pois as (
    select * from {{ ref('points_of_interest', v=2) }}
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
                        'confidence', confidence,
                        'description', description,
                        'lp_section', lp_section,
                        'section_mile', section_mile,
                        'placement', placement,
                        'source_url', source_url,
                        'position_error_m', position_error_m,
                        'off_trail_miles', off_trail_miles,
                        'water_reliability', water_reliability,
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
