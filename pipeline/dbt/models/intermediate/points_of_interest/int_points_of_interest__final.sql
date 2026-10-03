-- int_points_of_interest__final: the points of interest mart's rows before
-- their row dates, every contracted column but _first_seen_at and _changed_at.
-- This is what models/marts/points_of_interest/points_of_interest.sql held
-- until decision 57; int_points_of_interest__history snapshots it, and the mart
-- reads that snapshot.
--
-- Every POI a phone is given, one row each, keyed by the id it publishes
-- under (`poi_id`, held stable by the identity ledger for the A.T. family):
-- the A.T. family's POIs (export_poi.py's eight poi_<type>.geojson files,
-- `phone_files` 'poi_by_type'), the other organizations'
-- (export_nearby_poi.py's nearby_poi.geojson, 'nearby_poi'), and the
-- tombstones of every POI the ledger has retired (export_retired_poi.py's
-- retired_poi.geojson, 'retired_poi'). The pub_ writers read nothing else.
--
-- Only rows whose source may publish, from int_sources__publication, the one
-- home of may_publish: the live rows were already held to it before any
-- merge (int_points_of_interest__publishable), and this join is the mart's
-- own statement of it, which also covers the tombstones (source
-- `poi_identity`).
--
-- THE SAFETY FIELDS (pipeline/ELT.md, "The eleven marts"), each a test in
-- _points_of_interest__models.yml:
-- - `mile` only on an A.T. POI that is on the A.T.: null where `not_on_at`
--   names another organization's trail;
-- - `capacity` null or at least 1: absent is unknown, never zero;
-- - `water_distance_ft` above 0, and null exactly where
--   `water_distance_source` is: a distance never ships without the source
--   the phone prints its tilde from (42 of the 305 published distances are
--   OSA_Field_Estimate);
-- - `confidence` high or low on every live POI.
--
-- GEOMETRY IS TEXT HERE: `geom_geojson`, an RFC 7946 Point in lon/lat at the
-- precision the row's phone file prints today, because dbt 2.0.6 cannot
-- build a contracted model with a GEOMETRY column (.claude/skills/dbt/
-- SKILL.md, "Contracts, and the traps in them"). A poi_<type>.geojson
-- coordinate is what GDAL's GeoJSON writer prints (gdal_geojson_coordinate()),
-- which is not always the double the source holds: -74.29599999999999 prints
-- as -74.296. The other two files print a coordinate as json.dumps does,
-- every digit, so their text is the double itself. A coordinate that moves
-- is a location error, so the pub_ writers copy this text and never
-- re-derive it. `lat` and `lon` are the source's own doubles.
with described as (
    select * from {{ ref('int_points_of_interest__described') }}
),

miles as (
    select * from {{ ref('int_points_of_interest__miles') }}
),

retired_rows as (
    select * from {{ ref('int_points_of_interest__retired') }}
),

publication as (
    select * from {{ ref('int_sources__publication') }}
),

trailheads as (
    select * from {{ ref('int_points_of_interest__trailheads') }}
),

photos as (
    select * from {{ ref('int_points_of_interest__photos') }}
),

live as (
    select
        described.poi_id,
        described.poi_key,
        described.phone_files,
        described.poi_type,
        described.trail_id,
        described.source,
        described.source_feature_id,
        described.source_feature_id_json,
        described.name,
        described.lat,
        described.lon,
        cast(miles.mile as double) as mile,
        described.not_on_at,
        described.confidence,
        cast(described.capacity as integer) as capacity,
        cast(described.water_distance_ft as integer) as water_distance_ft,
        described.water_distance_source,
        described.description,
        described.nearby,
        described.lp_section,
        described.section_mile,
        described.placement,
        described.source_url,
        described.position_error_m,
        described.off_trail_miles,
        described.water_reliability,
        described.site_id,
        described.site_role,
        described.site_name,
        cast(null as varchar) as retired,
        cast(null as varchar) as superseded_by,
        described.record_order,
        described.club,
        described.source_key,
        described._loaded_at
    from described
    left join miles on described.poi_id = miles.poi_id
),

tombstones as (
    select
        poi_id,
        poi_key,
        'retired_poi' as phone_files,
        poi_type,
        cast(null as varchar) as trail_id,
        source,
        source_feature_id,
        to_json(source_feature_id) as source_feature_id_json,
        name,
        lat,
        lon,
        cast(null as double) as mile,
        cast(null as varchar) as not_on_at,
        cast(null as varchar) as confidence,
        cast(null as integer) as capacity,
        cast(null as integer) as water_distance_ft,
        cast(null as varchar) as water_distance_source,
        cast(null as varchar) as description,
        cast(null as json) as nearby,
        cast(null as integer) as lp_section,
        cast(null as double) as section_mile,
        cast(null as varchar) as placement,
        cast(null as varchar) as source_url,
        cast(null as integer) as position_error_m,
        cast(null as double) as off_trail_miles,
        cast(null as varchar) as water_reliability,
        cast(null as varchar) as site_id,
        cast(null as varchar) as site_role,
        cast(null as varchar) as site_name,
        retired,
        superseded_by,
        -- export_retired_poi.py's build() sorts the tombstones by id.
        row_number() over (order by poi_id) as record_order,
        club,
        source_key,
        _loaded_at
    from retired_rows
),

unioned as (
    select * from live
    union all
    select * from tombstones
)

select
    unioned.poi_id,
    unioned.poi_key,
    unioned.phone_files,
    unioned.poi_type,
    unioned.trail_id,
    unioned.source,
    unioned.source_feature_id,
    unioned.source_feature_id_json,
    unioned.name,
    unioned.lat,
    unioned.lon,
    cast(
        json_object(
            'type', 'Point',
            'coordinates',
            case
                when unioned.phone_files = 'poi_by_type'
                    then
                        list_value(
                            {{ gdal_geojson_coordinate('unioned.lon') }},
                            {{ gdal_geojson_coordinate('unioned.lat') }}
                        )
                else list_value(unioned.lon, unioned.lat)
            end
        ) as varchar
    ) as geom_geojson,
    unioned.mile,
    unioned.not_on_at,
    unioned.confidence,
    unioned.capacity,
    unioned.water_distance_ft,
    unioned.water_distance_source,
    unioned.description,
    unioned.nearby,
    -- PO36: the Long Path guide's own fields, on its waypoints only.
    unioned.lp_section,
    unioned.section_mile,
    unioned.placement,
    unioned.source_url,
    unioned.position_error_m,
    unioned.off_trail_miles,
    unioned.water_reliability,
    -- PO24 and PO38: the card photo and gallery through the face gate
    -- (int_points_of_interest__photos), on the A.T. family's POIs, which are
    -- the only ones export_poi.py attaches photos to. Null is "no photo",
    -- which is what a phone shows for every POI that has none to show.
    photos.photo_key,
    photos.photo_page_url,
    photos.photo_author,
    photos.photo_license,
    photos.photo_taken,
    cast(photos.photos as json) as photos,
    unioned.site_id,
    unioned.site_role,
    unioned.site_name,
    -- PO34: set on a trailhead whose every trail line within 100 m is
    -- closed (int_points_of_interest__trailheads); null is "not marked".
    trailheads.trails_closed_within_m,
    unioned.retired,
    unioned.superseded_by,
    unioned.record_order,
    unioned.club,
    unioned.source_key,
    unioned._loaded_at
from unioned
inner join publication on unioned.source_key = publication.source_key
left join trailheads on unioned.poi_id = trailheads.poi_id
left join photos
    on
        unioned.phone_files = 'poi_by_type'
        and unioned.poi_id = photos.poi_id
where publication.may_publish
