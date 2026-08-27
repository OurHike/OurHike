-- OPRHP's TEMPORARY trail-closure polygons. A safety surface: of everything
-- Phase D stages, this is the layer whose freshness matters most
-- (CLAUDE.md's closures path).
--
-- TWO COLUMNS, AND THAT IS EVERYTHING THE REGISTRY EVIDENCES. sources.json
-- records a count (4 features on 2026-08-18), a last-edit date, and two
-- field names reached through `reason_field` (Name) and `place_field`
-- (Descript). No full field list was ever measured for this layer, so this
-- model stages those two and stops. Instruction, not modesty: a closure
-- model with invented columns is the worst possible place for one.
-- What would settle it is a field-metadata read of the service.
--
-- AN HONEST COUNT OF ZERO IS THE EXPECTED ANSWER IN A GOOD WEEK. The entry
-- declares `may_be_empty`, which is why this layer could never sit behind
-- fetch_all.py's non-empty completeness gate - and it is also why no test
-- here asserts a row count floor. An empty closures table means nothing is
-- closed; it does not mean the fetch broke, and a test that could not tell
-- those apart would be red every good week.
with source as (
    select * from {{ source('oprhp', 'raw_oprhp__oprhp_trail_closures') }}
)

select
    name as closure_reason,
    descript as closure_place,
    _loaded_at as loaded_at
from source
