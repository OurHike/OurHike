{{ config(materialized='table') }}
-- Every staged row of every layer a POI file publishes from, one row each,
-- unfiltered and unclassified: the A.T. family export_poi.py writes as the
-- eight poi_<type>.geojson files, the other organizations' layers
-- export_nearby_poi.py writes as nearby_poi.geojson, decision 54's wave 1
-- point layers, which no exporter reads, and GATC's water list placed from
-- its miles (decision 75; the last two branches). A row here is
-- not a publishable POI; int_points_of_interest__classified and
-- int_points_of_interest__publishable decide that.
--
-- A ROW IS ITS SOURCE'S PROPERTIES, AS JSON. Each branch keeps its staging
-- model's key, its point and its load stamp as columns and every other
-- column in `properties`, keyed by dlt's lowercase name. The fields a rule
-- reads are named in the poi_sources seed (export_poi.py's field maps) and
-- in sources.json (export_nearby_poi.py's: id_field, name_field,
-- public_field, asset_field, facility_field), so the classifier reads each
-- by the name its own home gives it, as the Python does, rather than this
-- model retyping one column list per layer. A field a layer does not carry
-- reads as null, which is what properties.get() returns.
--
-- One branch per staged layer, and a UNION BY NAME, never by position: under
-- the positional union this replaces (int_pois_unioned), a swapped st_x and
-- st_y in one staging model put every DEC lean-to in Antarctica on a green
-- build (assert_pois_land_in_the_region_this_build_covers.sql says how).
-- assert_int_points_of_interest__unioned_matches_staging_sum holds the
-- branch list to the staging models it reads, row for row.
--
-- The last branch is not a staged layer: it is fetch_trail_water.py's site
-- water, which step_site_water.py derives into derived.site_water (PO07,
-- PO17), one point per shelter or campsite whose water the gates passed.
-- Its properties are the six load_trail_water() writes, under the same
-- names, and the poi_sources seed reads its id from `site_global_id`, so the
-- stream point publishes as `nhd_stream:<site GlobalID>` exactly as
-- export_poi.py names it; `source_row` is the site's place in the file. A site
-- the gates refused has no point and no row here: it publishes nothing.
--
-- ATC's bridges are staged and not here: their registry row reads
-- `reaches_hikers: false` since #1674 withdrew the crossing type, and
-- export_poi.py's DIRECT_SOURCES does not read them.
--
-- `source_row` is the row's place in its raw table where the staging model
-- carries it, which is every A.T. layer's: the order export_poi.py reads the
-- same file in, and so the tie-break its stable sorts fall back on. The
-- other organizations' staging models are not this family's, and nothing
-- export_nearby_poi.py publishes depends on its read order.
{%- set branches = [
    ('shelters', 'stg_atc__shelters', true),
    ('campsites', 'stg_atc__campsites', true),
    ('viewpoints', 'stg_atc__viewpoints', true),
    ('parking', 'stg_atc__parking', true),
    ('privies', 'stg_atc__privies', true),
    ('communities', 'stg_atc__communities', true),
    ('opentrail_at', 'stg_opentrail__waypoints', true),
    ('oprhp_facilities', 'stg_oprhp__facilities', true),
    ('dec_lean_tos', 'stg_dec__lean_tos', true),
    ('dec_primitive_campsites', 'stg_dec__primitive_campsites', true),
    ('dec_scenic_vistas', 'stg_dec__scenic_vistas', true),
    ('dec_firetowers', 'stg_dec__firetowers', true),
    ('dec_viewing_areas', 'stg_dec__viewing_areas', true),
    ('dec_parking_areas', 'stg_dec__parking_areas', true),
    ('dec_backcountry_features', 'stg_dec__backcountry_features', true),
    ('usfs_rec_sites', 'base_usfs__rec_sites', false),
    ('nyc_public_restrooms', 'base_nycparks__nyc_public_restrooms', false),
    ('nyc_drinking_fountains', 'base_nycparks__nyc_drinking_fountains', false),
] %}
{% for source_key, model, has_row in branches %}
select
    '{{ source_key }}' as source_key,
    staged.poi_key,
    {% if has_row %}staged.source_row{% else %}cast(null as bigint) as source_row{% endif %},
    staged.geom,
    -- json_merge_patch drops a member a patch sets to null, so this is
    -- the row without the two columns that travel beside it.
    json_merge_patch(to_json(staged), '{"geom": null, "source_row": null}')
        as properties,
    staged._loaded_at
from {{ ref(model) }} as staged
union all by name
{% endfor %}
-- OSM's water points (PO03): export_poi.py's unify_all_sources() reading
-- data/raw/osm_water.geojson, here step_osm_water's rows. The properties are
-- the file's own JSON, so `kind` and the reliability tags reach the
-- describer as describe_water() reads them, and a tag OSM does not carry is
-- absent. No row lands outside fixture mode until #1652 — Download OSM's
-- Geofabrik extracts at most once a month, into a private raw bucket that
-- outlives the 7-day Actions cache.
select
    'osm_water' as source_key,
    osm.osm_water_key as poi_key,
    cast(osm.feature_row as bigint) as source_row,
    case
        when osm.lon is not null and osm.lat is not null
            then st_point(osm.lon, osm.lat)
    end as geom,
    osm.properties,
    osm._loaded_at
from {{ ref('stg_derived__osm_water') }} as osm
union all by name
-- NYNJTC's Long Path guide (PO36): export_nearby_poi.py's guide_records(),
-- the records step_long_path_guide's build_records() made of the guide's
-- pages, whole, which the classifier reads as already unified (the
-- poi_sources seed's `unified`): their own type, confidence, id and name.
select
    'nynjtc_long_path_guide' as source_key,
    guide.long_path_guide_key as poi_key,
    cast(guide.record_row as bigint) as source_row,
    st_point(guide.lon, guide.lat) as geom,
    guide.record as properties,
    guide._loaded_at
from {{ ref('stg_derived__long_path_guide') }} as guide
union all by name
-- fetch_trail_water.py's site water (PO07, PO17), the step's verdicts, of
-- which only a site that has water publishes a point: export_poi.py's
-- load_trail_water(), reading data/raw/trail_water.json's `sites`. Its
-- properties are the ones that function hands unify_poi(), so the id is the
-- site's GlobalID and the description reads the stream's sources and flow.
select
    'nhd_stream' as source_key,
    site.site_water_key as poi_key,
    cast(site.site_row as bigint) as source_row,
    st_point(site.water_lon, site.water_lat) as geom,
    json_object(
        'site_global_id', site.atc_global_id,
        'stream_id', site.stream_id,
        'sources', site.sources,
        'name', site.water_name,
        'flow', site.flow,
        'flow_source', site.flow_source
    ) as properties,
    site._loaded_at
from {{ ref('stg_derived__site_water') }} as site
where site.has_water
union all by name
-- Decision 54's wave 1 point layers, every row of the clubs' registered
-- ArcGIS point layers that no exporter reads: int_points_of_interest__
-- club_points, which types each row from the club_poi_types seed and holds
-- it back by the layer_rules seed. Each is a record already typed, as the
-- Long Path guide's are: its layer's own properties with the poi_type,
-- confidence, published id and name that model set written over them, and
-- its `rule_drop_reason` where a rule holds it back, which the classifier
-- reads first. A null member is dropped by json_merge_patch, which is what
-- a null name or type should be: absent.
select
    club.source_key,
    club.poi_key,
    cast(null as bigint) as source_row,
    st_geomfromtext(club.geom_wkt) as geom,
    json_merge_patch(
        club.properties,
        json_object(
            'id', club.derived_id,
            'source_id', club.source_id,
            'name', club.name,
            'poi_type', club.poi_type,
            'confidence', club.confidence,
            'rule_drop_reason', club.rule_drop_reason
        )
    ) as properties,
    club._loaded_at
from {{ ref('int_points_of_interest__club_points') }} as club
union all by name
-- GATC's water list (decision 75), int_points_of_interest__gatc_water's
-- records: each A.T. source placed on ATC's mile axis from GATC's own mile,
-- typed water at low confidence there, with its hold reason where one holds
-- it (the approach trail, a mile no piece carries, GATC's own "dry", a
-- namesake past the bound), read as the wave 1 records above are. A held
-- source with no point arrives with a null geom; the classifier reads its
-- rule_drop_reason first.
select
    gatc.source_key,
    gatc.poi_key,
    cast(null as bigint) as source_row,
    st_geomfromtext(gatc.geom_wkt) as geom,
    json_merge_patch(
        gatc.properties,
        json_object(
            'id', gatc.derived_id,
            'source_id', gatc.source_id,
            'name', gatc.name,
            'poi_type', gatc.poi_type,
            'confidence', gatc.confidence,
            'rule_drop_reason', gatc.rule_drop_reason
        )
    ) as properties,
    gatc._loaded_at
from {{ ref('int_points_of_interest__gatc_water') }} as gatc
