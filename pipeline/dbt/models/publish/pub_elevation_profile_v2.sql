{{ config(format='json', location='elevation_profile_v2.json') }}
-- v2/elevation_profile.json (decision 44's v2 of the elevation mart), the
-- A.T. elevation profile packed as columns of whole numbers, delta-coded
-- (pipeline/ELT.md, "Making the download smaller", tier (a)). The same
-- samples as v1's elevation_profile.json, in the same order, and the same
-- values: client/src/lib/elevationProfile.ts's parseProfile() decodes it
-- back to the numbers v1 carries, and parity.py's elevation_v2 family holds
-- the two files equal, record by record.
--
-- THE FILE, one object:
--   "format": 2, which is how a reader tells it from v1's bare array;
--   "d_milli_mi": the samples' miles in thousandths of a mile, the first as
--     itself and every later one as its step from the sample before;
--   "e_deci_ft": the samples' elevations in tenths of a foot, null where the
--     DEM has no answer (never 0), and every other one as its step from the
--     last sample before it that has an elevation, the first such as itself;
--   "part_start": the index, from 0, of every sample that begins a piece of
--     the centerline (#559), ascending. v1 writes "part_start": true on
--     exactly those samples.
-- A sample's mile is d_milli_mi[0] + ... + d_milli_mi[i], over 1,000.
--
-- Empty, it writes all three lists as []: the aggregate below is one row
-- whatever the mart holds, as v1's writer's is.
with profile as (
    select
        seq,
        distance_milli_mi,
        elevation_deci_ft,
        part_start,
        row_number() over (order by seq) - 1 as sample_index
    from {{ ref('elevation', v=2) }}
    where line_id = 'AT'
),

-- The elevations that exist, each against the one before it: a null is not
-- a step, so the step after a gap is taken from the last known elevation.
elevation_steps as (
    select
        seq,
        elevation_deci_ft
        - lag(elevation_deci_ft, 1, 0) over (order by seq) as elevation_step
    from profile
    where elevation_deci_ft is not null
),

coded as (
    select
        profile.seq,
        profile.sample_index,
        profile.part_start,
        profile.distance_milli_mi
        - lag(profile.distance_milli_mi, 1, 0) over (order by profile.seq)
            as distance_step,
        elevation_steps.elevation_step
    from profile
    left join elevation_steps on profile.seq = elevation_steps.seq
)

-- The struct's fields as the file's top-level members, in this order: COPY's
-- JSON format writes a row's columns, so the writer selects them (ELT.md:
-- the packed writers select packed.*).
select packed.*  -- noqa: AM04
from (
    select
        {
            'format': 2,
            'd_milli_mi': coalesce(list(distance_step order by seq), []),
            'e_deci_ft': coalesce(list(elevation_step order by seq), []),
            'part_start': coalesce(
                list(sample_index order by seq) filter (where part_start),
                []
            )
        } as packed
    from coded
) as wrapped
