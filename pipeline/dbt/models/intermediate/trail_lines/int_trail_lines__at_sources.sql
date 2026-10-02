-- The A.T. build's line sources (TL01), export_trails.load_line_sources():
-- every registry entry carrying blaze metadata, a `blaze_field` or a
-- `blaze_default` key, that is not another organization's layer. Today that is
-- centerline (blaze_default "White") and side_trails (blaze_field "Blaze"),
-- in the registry's order, which is the order export_trails.py reads them.
--
-- `is_external_source` is lib/source_registry.py's test: an
-- external_arcgis_layer or a socrata_geojson_layer, with a source that names
-- no kind defaulting to arcgis_feature_layer. Those layers are the network's
-- (int_trail_lines__network_sources), clipped to their own ground.
--
-- The Python finds a source's features at data/raw/<key>.geojson, so a new
-- entry here would be read with no other change. A model cannot read a file
-- it has no staging model for, so the test on `staged` stops the build
-- instead of letting such a source vanish.
with registry as (
    select * from {{ ref('stg_registry__sources') }}
)

select
    source_key,
    file_row,
    json_extract_string(entry, '$.blaze_field') as blaze_field,
    json_extract_string(entry, '$.blaze_default') as blaze_default,
    source_key in ('centerline', 'side_trails') as staged
from registry
where
    (
        list_contains(json_keys(entry), 'blaze_field')
        or list_contains(json_keys(entry), 'blaze_default')
    )
    and coalesce(kind, 'arcgis_feature_layer')
    not in ('external_arcgis_layer', 'socrata_geojson_layer')
