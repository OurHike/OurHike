-- reference/water_distance.json (extract/atc/points_of_interest.py): every
-- A.T. shelter and campsite with how far ATC's Campsite Sustainability Index
-- puts the nearest water, keyed, nothing filtered or joined.
-- build_water_distance.py builds the file and its `--check` re-derives it;
-- a person reviews it as a diff, and that review is the gate.
--
-- Key: poi_id, unique on all 512 rows (pipeline/ELT.md, "One key per
-- table"): the POI identity ledger's id for the site, which
-- build_water_distance.py resolves and int_points_of_interest__water joins on
-- (#1729 - The water-distance join is keyed by bare ATC GlobalID, nothing
-- runs its --check, and the CSI figure carries no as-of date).
with source as (
    select * from {{ source('atc', 'raw_atc__water_distance') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'reference/water_distance.json'",
            'poi_id',
        ]) }} as water_distance_key,
        layer,
        poi_id,
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
