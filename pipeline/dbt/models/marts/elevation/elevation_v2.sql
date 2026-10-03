-- The elevation mart's v2 (decision 44), for the packed
-- elevation_profile.json that pub_elevation_profile_v2 writes at
-- v2/elevation_profile.json (pipeline/ELT.md, "Making the download
-- smaller", tier (a): "columnar delta-coded integers"). The same rows as v1,
-- one per 25 m sample, with each number as the whole count of its own
-- published unit instead of a decimal: miles as thousandths of a mile and
-- feet as tenths of a foot.
--
-- LOSSLESS BY CONSTRUCTION. v1's distance_mi is a decimal(8,3) and its
-- elevation_ft a decimal(6,1), so times 1,000 and times 10 each give a whole
-- number exactly, in decimal arithmetic, with no double in between. The
-- phone divides back (client/src/lib/elevationProfile.ts's parseProfile),
-- and an IEEE division of a whole number by 1,000 or 10 is the double
-- nearest the decimal, which is what JSON.parse makes of v1's text (Reasoned
-- from IEEE 754's correctly rounded division; parity.py's elevation_v2
-- family checks it on the fixture warehouse, record by record).
--
-- elevation_deci_ft is null exactly where v1's elevation_ft is: no DEM
-- answer at the sample, never 0 (pipeline/ELT.md's safety table).
--
-- Why a version and not a new column on v1: distance_mi and elevation_ft
-- are not here, so this is a removed column and a new type, which decision
-- 44 ships as a new version beside v1 (check_contract_versions.py). v1 stays
-- the mart's latest version, so every unpinned ref still reads v1: the two
-- singular tests under tests/singular/elevation/ that read elevation_ft.
with v1 as (
    select * from {{ ref('elevation', v=1) }}
)

select
    line_id,
    seq,
    cast(distance_mi * 1000 as bigint) as distance_milli_mi,
    cast(elevation_ft * 10 as integer) as elevation_deci_ft,
    -- v1's DEM metres, unrounded, as v1 carries them (no v2 file prints it).
    elevation_m,
    part_start,
    club,
    source_key,
    _loaded_at,
    -- v1's row dates (decision 57): v2's rows are v1's, printed for v2's
    -- files, so a change to a v1 column v2 drops moves them too.
    _first_seen_at,
    _changed_at
from v1
