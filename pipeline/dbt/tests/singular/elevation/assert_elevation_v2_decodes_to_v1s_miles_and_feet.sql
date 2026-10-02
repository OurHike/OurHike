-- elevation v2's whole thousandths of a mile and tenths of a foot, each
-- divided back by 1,000 or 10, are the doubles a phone reads out of v1's
-- elevation_profile.json, on every sample (stage 6 of #1793): what
-- client/src/lib/elevationProfile.ts does to v2/elevation_profile.json, and
-- IEEE 754 rounds the division to the double nearest the quotient, as
-- JSON.parse rounds v1's decimal text. An elevation is null in v2 exactly
-- where it is in v1, so a DEM gap stays unknown and never becomes 0.
-- Elevation and miles are safety fields (pipeline/ELT.md, "The eleven
-- marts"), so any row fails the build. Returns no rows.
with v1 as (
    select
        line_id,
        seq,
        cast(distance_mi as double) as distance_mi,
        cast(elevation_ft as double) as elevation_ft
    from {{ ref('elevation', v=1) }}
),

v2 as (
    select
        line_id,
        seq,
        distance_milli_mi / 1000 as distance_mi,
        elevation_deci_ft / 10 as elevation_ft
    from {{ ref('elevation', v=2) }}
)

select
    v1.line_id,
    v1.seq,
    v1.distance_mi,
    v2.distance_mi as v2_distance_mi,
    v1.elevation_ft,
    v2.elevation_ft as v2_elevation_ft
from v1
full outer join v2 on v1.line_id = v2.line_id and v1.seq = v2.seq
where
    v1.seq is null
    or v2.seq is null
    or v1.distance_mi != v2.distance_mi
    or (v1.elevation_ft is null) != (v2.elevation_ft is null)
    or v1.elevation_ft != v2.elevation_ft
