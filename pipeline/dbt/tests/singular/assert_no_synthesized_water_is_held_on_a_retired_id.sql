-- Every shelter or campsite whose synthesized water point
-- int_points_of_interest__water holds because its id is a retired ledger row
-- (that model's header), one row each, at warn: the anchor, the retired id
-- and the release that retired it. For a person to write a `same` override
-- where it is the same place returning (reconcile_poi_identity.py:585-592's
-- door back in), or to wait for real water to land at the site (#1652 —
-- Download OSM's Geofabrik extracts at most once a month, into a private raw
-- bucket that outlives the 7-day Actions cache, and trail_water.json). Until
-- then the card keeps CSI's distance and the site shows no water member.
--
-- WHERE THE ROWS ARE. dbt 2.0.6 logs a warned test by name only, with no
-- count and no rows (measured 2026-10-04 on the fixture build, `dbt build`
-- and `dbt test`), so the log says that anchors were held, not which.
-- store_failures keeps the rows in the warehouse, as
-- dbt_test__audit.assert_no_synthesized_water_is_held_on_a_retired_id,
-- which build-reference.yml stores in the step cache with its manifest.
--
-- Measured 2026-10-02 on ATC's live layers against the committed ledger: 21
-- (assert_no_live_poi_reuses_a_retired_id.sql's header).
{{ config(severity='warn', store_failures=true) }}

with held as (
    select
        poi_id,
        name,
        held_csi_water_id
    from {{ ref('int_points_of_interest__water') }}
    where held_csi_water_id is not null
),

ledger as (
    select
        poi_id,
        retired
    from {{ ref('base_ourhike__poi_identity') }}
)

select
    held.poi_id,
    held.name,
    held.held_csi_water_id,
    ledger.retired
from held
left join ledger on held.held_csi_water_id = ledger.poi_id
