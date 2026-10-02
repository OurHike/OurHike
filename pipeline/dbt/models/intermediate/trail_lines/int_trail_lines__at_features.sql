{{ config(materialized='table') }}
-- Every feature of the A.T.'s line sources, as export_trails.py's
-- build_trail_records() makes them, before the corridor clip: one row per
-- staged feature, in the registry's source order and then the layer's own.
--
-- TL04, LINES ONLY: a feature whose geometry is a LineString or a
-- MultiLineString is kept, and anything else, a missing geometry included,
-- is skipped. The Python warns per feature; `has_line_geometry` keeps the
-- row so the warn test on it names each one, and the clip reads only the
-- rows that have one. One live side trail has none (2026-10-02).
--
-- TL05, THE ID: lib/feature_id.py's chain, the GlobalID, else the feature's
-- own `id`, else `generated-<index>` with the feature's place in its layer.
-- ArcGIS serves the OBJECTID as that `id` (stg_atc__side_trails' objectid
-- says where that was measured), so the second step reads the OBJECTID, and
-- the third the row's place in the raw table. The centerline's segment ids
-- are never published (its chains are numbered instead), so it takes no
-- OBJECTID step.
--
-- The name is the layer's `Name`, and the blaze int_trail_lines__blazes's,
-- which is export_trails.normalize_source_features()'s decode.
--
-- THE GEOMETRY IS WKT TEXT, `geom_wkt`, from here to the mart: a dbt 2.0.6
-- unit test cannot run on a model whose output holds a GEOMETRY ("BinaryView
-- is not supported for DuckDB", measured 2026-10-02 on this model with no
-- geometry in its expected rows), and every model from here to the mart has
-- one. ST_AsText prints the fewest digits that read back to the same double,
-- so ST_GeomFromText gives each vertex back to the bit.
with sources as (
    select * from {{ ref('int_trail_lines__at_sources') }}
),

blazes as (
    select * from {{ ref('int_trail_lines__blazes') }}
),

staged as (
    select
        trail_segment_key,
        'centerline' as source_key,
        coalesce(source_id, 'generated-' || source_row) as feature_id,
        name,
        cast(null as varchar) as trail_type,
        cast(null as double) as length_ft,
        geom,
        source_row,
        loaded_at
    from {{ ref('stg_atc__centerline_segments') }}
    union all
    select
        trail_segment_key,
        'side_trails' as source_key,
        coalesce(
            source_id, cast(objectid as varchar), 'generated-' || source_row
        ) as feature_id,
        name,
        trail_type,
        length_ft,
        geom,
        source_row,
        loaded_at
    from {{ ref('stg_atc__side_trails') }}
)

select
    staged.trail_segment_key,
    staged.source_key,
    -- The extract folder that landed both layers (pipeline/extract/atc/).
    'atc' as club,
    sources.file_row as source_order,
    staged.source_row,
    staged.feature_id,
    staged.source_key || ':' || staged.feature_id as trail_line_id,
    staged.name,
    blazes.blaze_color,
    staged.trail_type,
    staged.length_ft,
    st_astext(staged.geom) as geom_wkt,
    coalesce(
        st_geometrytype(staged.geom) in ('LINESTRING', 'MULTILINESTRING'),
        false
    ) as has_line_geometry,
    staged.loaded_at as _loaded_at
from staged
inner join sources on staged.source_key = sources.source_key
-- A left join, so a feature int_trail_lines__blazes has no row for fails
-- the not_null test on blaze_color rather than vanishing from the map.
left join blazes on staged.trail_segment_key = blazes.trail_segment_key
