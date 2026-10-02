{{ config(materialized='table') }}
-- The tombstones: every POI id the identity ledger has ever retired, where
-- it was and what happened to it (PO26, export_retired_poi.py's
-- retired_rows() and tombstone(), #673). One row per retired ledger row.
--
-- Every retired row, whenever it was retired, never pruned by age:
-- lib/poi_identity.py's retired_rows() answers "how long a tombstone
-- publishes" with "forever", on its own measurement of what a tombstone
-- costs a first fetch. A retired row is one whose `retired` the ledger
-- writes; on reference/poi_identity.json no row writes it as null (5,412
-- retired, 3,151 live, read 2026-10-02), which is the one case where the
-- Python's key-presence test and this null test could disagree.
--
-- `superseded_by` is the pointer a hiker's photos follow to the place that
-- took this one's place, and resolves_to says whether it reaches a live row
-- (lib/poi_identity.py's resolve(), followed transitively and stopping at a
-- cycle). One that resolves to nothing is a broken promise, and this
-- model's test refuses the build over it, as export_retired_poi.py's main()
-- refuses to write the file. On no row on 2026-10-02: no retired row
-- carries a successor.
--
-- The source is the ledger's own (poi_identity, in the
-- unregistered_publishing_sources seed): a tombstone tells a phone that a
-- POI it holds was removed, whatever source first published it.
with recursive ledger as (
    select * from {{ ref('base_ourhike__poi_identity') }}
),

successors (poi_id, step, current_id, seen) as (
    select
        poi_id,
        0,
        superseded_by,
        [poi_id]
    from ledger
    where
        retired is not null
        and superseded_by is not null
    union all
    select
        successors.poi_id,
        successors.step + 1,
        next_row.superseded_by,
        list_append(successors.seen, successors.current_id)
    from successors
    inner join ledger as next_row on successors.current_id = next_row.poi_id
    where
        next_row.retired is not null
        and next_row.superseded_by is not null
        and not list_contains(successors.seen, successors.current_id)
),

resolved as (
    -- The last id each chain reaches, kept only where that id is a live row.
    select
        successors.poi_id,
        live.poi_id as resolves_to
    from successors
    inner join ledger as live
        on
            successors.current_id = live.poi_id
            and live.retired is null
    qualify
        row_number()
            over (partition by successors.poi_id order by successors.step desc)
        = 1
)

select
    ledger.poi_id,
    ledger.poi_identity_key as poi_key,
    'poi_identity' as source_key,
    'ourhike' as club,
    ledger.poi_type,
    ledger.source,
    ledger.source_feature_id,
    ledger.name,
    ledger.latitude as lat,
    ledger.longitude as lon,
    ledger.retired,
    ledger.superseded_by,
    resolved.resolves_to,
    ledger._loaded_at
from ledger
left join resolved on ledger.poi_id = resolved.poi_id
where ledger.retired is not null
