-- What the DEM reads at each elevation sample point: step_dem_sampling's
-- table (pipeline/step_dem_sampling.py), staged like any table a source
-- lands. The step reads int_elevation__sample_points; int_elevation__profile
-- joins these rows back to it on the line, the sample and the point itself,
-- so a row read at any other point never lends a sample its elevation.
with source as (
    -- The step writes the point as GeoJSON text, as dlt lands every
    -- geometry; cast here, as decision 40 has staging do.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('derived', 'dem_samples') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'dem_samples'",
            'line_id',
            'sample_index',
        ]) }} as dem_sample_key,
        line_id,
        sample_index,
        st_x(geom) as lon,
        st_y(geom) as lat,
        elevation_m,
        _loaded_at as loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='dem_sample_key', order_by='sample_index'
) }}
