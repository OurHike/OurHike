{{ config(materialized='table') }}
-- Every staged row of every layer a POI file publishes from, one row each,
-- unfiltered and unclassified: the A.T. family export_poi.py writes as the
-- eight poi_<type>.geojson files, and the other organizations' layers
-- export_nearby_poi.py writes as nearby_poi.geojson. A row here is not a
-- publishable POI; int_points_of_interest__classified and
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
{% if not loop.last %}union all by name{% endif %}
{% endfor %}
