-- The U.S. Census Bureau's TIGER/Line states (sources.json
-- `census_tiger_states`, extract/_shared/census/states.py): every row, keyed
-- and deduped (decision 40), with nothing filtered and nothing joined.
--
-- Key: `stusps`, the state's two-letter code, unique and non-null on 56 of 56
-- records read 2026-10-04.
--
-- The fixture warehouse never holds this table (fixture mode cannot serve a
-- binary shapefile), so it is read through raw_or_empty() and reads as no
-- rows there.
with source as (
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ raw_or_empty(
        source('census', 'raw_census__census_tiger_states'),
        ['geometry', 'stusps', 'name', 'feature_index:bigint']
    ) }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'census_tiger_states'",
            'stusps',
        ]) }} as state_key,
        source.*
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='state_key', order_by='_dlt_id'
) }}
