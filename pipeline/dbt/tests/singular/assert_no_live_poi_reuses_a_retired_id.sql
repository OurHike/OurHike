-- No POI publishes live under an id the identity ledger has retired: ids
-- are never reused (reconcile_poi_identity.py:21). Today that is held
-- upstream of every export: reconcile_poi_identity.py:585-592 holds a record
-- that "re-presents the key of a RETIRED row", and :928-930 exits 2, so
-- the publish stops until a person writes a `same` override. The dbt build
-- runs no reconcile (PO22 stays a Python step), so this is its hold, and it
-- names what the mart's unique test on poi_id would only count. Fails by
-- returning each such id with the release that retired it.
--
-- Measured 2026-10-02 on ATC's live layers and opentrail's live feed against
-- the committed ledger: 21 synthesized water points (source atc_csi) did,
-- each retired on 2026-08-19, the day after it was first seen. Monthly run
-- 13 (refresh-reference.yml run 37182708502) failed
-- int_points_of_interest__final's unique poi_id test on 21 ids live and
-- tombstoned at once, the same count; this test was skipped there, so that
-- log does not say which ids. The
-- ledger's live rows hold 201 osm_water and 39 nhd_stream points, which this
-- build does not land yet (pipeline/ELT.md's PO03 and PO07), and a real
-- water point in a site stops synthesis, so the likeliest reading is that
-- those sites had one then and have none here (Reasoned; a build with OSM
-- and trail water landed would settle it).
--
-- Synthesized points are now held upstream: int_points_of_interest__water
-- makes none under a retired id, and
-- assert_no_synthesized_water_is_held_on_a_retired_id.sql lists the held
-- anchors at warn. This stays an error for every other collision, such as a
-- layer whose feature re-presents a retired key.
with live as (
    select
        poi_id,
        source,
        name
    from {{ ref('points_of_interest', v=1) }}
    where phone_files != 'retired_poi'
),

tombstones as (
    select
        poi_id,
        retired
    from {{ ref('points_of_interest', v=1) }}
    where phone_files = 'retired_poi'
)

select
    live.poi_id,
    live.source,
    live.name,
    tombstones.retired
from live
inner join tombstones on live.poi_id = tombstones.poi_id
