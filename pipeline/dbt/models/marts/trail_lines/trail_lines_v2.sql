-- The trail_lines mart's v2 (decision 44), for the packed trail_miles.json
-- that pub_trail_miles_v2 writes at v2/trail_miles.json (pipeline/ELT.md,
-- "Making the download smaller", tier (a): "each vertex array as milli-mile
-- deltas"). The same rows as v1, every column as v1 has it, except that a
-- centerline chain's vertex miles are whole thousandths of a mile
-- (vertex_milli_miles) instead of v1's doubles (vertex_miles).
--
-- LOSSLESS, AND TESTED RATHER THAN ASSUMED. v1's vertex_miles are rounded
-- at var('trail_lines_mile_decimals'), 3, half to even as numpy rounds them
-- (int_trail_lines__mile_axis), so each is the double nearest some whole
-- number of thousandths. Times 1,000 that double lands within a billionth of
-- the whole number, nowhere near a half, so the cast to bigint (which rounds
-- to nearest) takes the whole number itself. A mile that was NOT so rounded
-- would come back as a different double, and the singular test
-- assert_trail_lines_v2_vertex_milli_miles_decode_to_v1s_vertex_miles fails
-- the build on it: it divides each whole number back by 1,000, which IEEE
-- 754 rounds correctly to the nearest double, and compares it with v1's. So
-- if var('trail_lines_mile_decimals') ever moves off 3, that test is what
-- says thousandths no longer hold the miles.
--
-- Why a version: vertex_miles is not here, a removed column, which decision
-- 44 ships beside v1 (check_contract_versions.py). v1 stays the latest
-- version, so every unpinned ref still reads v1: int_places__lines and the
-- places unit tests that mock it.
with v1 as (
    select * from {{ ref('trail_lines', v=1) }}
)

select
    trail_line_id,
    club,
    source_key,
    _loaded_at,
    line_kind,
    feature_order,
    name,
    blaze_color,
    trail_status,
    trail_status_basis,
    closure_kind,
    closure_reason,
    closure_source,
    duplicate_of,
    geom_geojson,
    length_m,
    published_length_m,
    list_transform(
        vertex_miles, lambda mile: cast(mile * 1000 as bigint)
    ) as vertex_milli_miles,
    monotonic_breaks,
    spur_length_ft,
    spur_destination_poi_id,
    spur_destination_distance_m,
    spur_junction_mile
from v1
