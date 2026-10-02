-- reference/water_distance.json (extract/atc/points_of_interest.py): every
-- A.T. shelter and campsite with how far ATC's Campsite Sustainability Index
-- puts the nearest water, keyed (decision 40), nothing filtered or joined.
-- build_water_distance.py builds the file and its `--check` re-derives it;
-- a person reviews it as a diff, and that review is the gate (PO14).
--
-- Key: atc_global_id, unique on all 512 rows (pipeline/ELT.md, "One key per
-- table").
with source as (
    select * from {{ source('atc', 'raw_atc__water_distance') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'reference/water_distance.json'",
            'atc_global_id',
        ]) }} as water_distance_key,
        layer,
        atc_global_id,
        atc_name,
        distance_ft,
        listed_distance_ft,
        provenance,
        unresolved,
        csi_rims_id,
        csi_location,
        match as csi_match,
        offset_m,
        _row as file_row,
        _loaded_at,
        _dlt_id
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='water_distance_key', order_by='_dlt_id'
) }}
