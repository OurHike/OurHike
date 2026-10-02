-- NYNJTC's Hike Finder export (extract/nynjtc/suggested_hikes.py), one row
-- per hike as lib/hikefinder.py's parse_hike() reads its page, keyed
-- (decision 40), with nothing filtered and nothing joined. The parse runs at
-- the edge (SH01: an HTML parse is extraction), so a coordinate outside the
-- NYNJTC box already arrives as a null `start`. Reading the hike is the work
-- of int_suggested_hikes__hike_finder; forming its route is
-- step_form_route.py's.
--
-- The nested values stay JSON, as the extract lands them (max_table_nesting
-- 0): `start` is {lat, lon, label}, and the prose and the tags are lists.
-- `gpx` is the published track as served, never parsed here.
--
-- Key: the export's own hike id.
with source as (
    select * from {{ source('nynjtc', 'raw_nynjtc__nynjtc_hike_finder') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'nynjtc_hike_finder'",
            'id',
        ]) }} as hike_finder_key,
        id as hike_number,
        name,
        source_url,
        summary,
        stated_miles,
        difficulty,
        estimated_hours,
        route_type,
        dogs,
        park,
        region,
        author,
        cast(start as json) as start_json,
        cast(features as json) as features_json,
        published_on,
        updated_on,
        cast(directions as json) as directions_json,
        cast(description as json) as description_json,
        cast(public_transport as json) as public_transport_json,
        has_published_route,
        gpx_url,
        gpx,
        cast(problems as json) as parse_problems_json,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='hike_finder_key', order_by='_dlt_id'
) }}
