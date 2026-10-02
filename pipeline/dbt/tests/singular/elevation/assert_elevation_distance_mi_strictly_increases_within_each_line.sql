-- distance_mi strictly increases along each line of the elevation mart
-- (pipeline/ELT.md, "The eleven marts": the singular test it names). The
-- phone binary-searches a profile by mile (client/src/lib/elevationProfile.ts,
-- firstIndexAtOrAfter), so a mile out of order puts the ribbon's window in
-- the wrong place, and a mile published twice counts its climb twice.
-- int_elevation__profile keeps a sample only past every earlier mile, so
-- this returns no rows; each row it returns is a sample at or behind the one
-- before it.
with ordered as (
    select
        line_id,
        seq,
        distance_mi,
        lag(distance_mi) over (partition by line_id order by seq)
            as previous_distance_mi
    from {{ ref('elevation') }}
)

select
    line_id,
    seq,
    distance_mi,
    previous_distance_mi
from ordered
where distance_mi <= previous_distance_mi
