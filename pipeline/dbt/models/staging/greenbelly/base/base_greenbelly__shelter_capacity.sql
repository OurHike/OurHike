-- reference/shelter_capacity.json (extract/_shared/greenbelly/
-- shelter_capacity.py): how many each A.T. shelter sleeps, from Greenbelly's
-- hiker-maintained list joined to ATC's shelters by name, keyed (decision
-- 40), nothing filtered or joined. build_shelter_capacity.py builds the file
-- and a person reviews it as a diff (PO12). A capacity nobody stands behind
-- is absent, never zero (PO13), and int_points_of_interest__enriched carries
-- that absence through.
--
-- Key: poi_id, the published id the file is keyed by, 280 of 280.
with source as (
    select * from {{ source('greenbelly', 'raw_greenbelly__shelter_capacity') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'reference/shelter_capacity.json'",
            'poi_id',
        ]) }} as shelter_capacity_key,
        poi_id,
        atc_name,
        capacity,
        listed_as,
        listed_capacity,
        unresolved,
        _row as file_row,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='shelter_capacity_key', order_by='_dlt_id'
) }}
