-- apply_area_closures() closes the network's lines against every layer the
-- registry marks `closure_areas` (export_nearby_trails.py's
-- closure_area_sources(), on external_sources()), and
-- int_trail_lines__network_area_closures reads one:
-- int_closures__oprhp_areas, `oprhp_trail_closures`. A second layer marked
-- for closed areas would be closed ground the export applies and the model
-- does not, so a trail inside it would ship open. Returns one row per marked
-- layer the model does not read; the fix is to read that layer's areas too.
select registry.source_key
from {{ ref('stg_registry__sources') }} as registry
where
    registry.kind in ('external_arcgis_layer', 'socrata_geojson_layer')
    and coalesce(
        json_extract_string(registry.entry, '$.closure_areas') = 'true', false
    )
    and registry.source_key != 'oprhp_trail_closures'
