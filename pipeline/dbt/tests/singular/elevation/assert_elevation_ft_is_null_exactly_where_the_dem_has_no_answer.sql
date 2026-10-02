-- A published elevation is null exactly where the DEM had no answer at the
-- sample, so a gap reaches the phone as unknown and never as 0 ft (pipeline/
-- ELT.md's safety table: "Null means no DEM coverage, never 0"). A 0 for a
-- gap would draw a cliff into the ribbon and count its climb into the
-- hiker's total; the phone reads a null as a break in the run instead
-- (client/src/lib/elevationProfile.ts, and walkProfile.ts for an edge).
-- Each published row is matched to the step's own row: an A.T. row through
-- int_elevation__profile, which carries its place in the walk, and an edge's
-- row directly, its seq being its sample_index. Returns no rows.
with at_published as (
    select
        elevation.line_id,
        elevation.seq,
        elevation.elevation_ft,
        profile.sample_index
    from {{ ref('elevation') }} as elevation
    inner join {{ ref('int_elevation__profile') }} as profile
        on
            elevation.line_id = profile.line_id
            and elevation.seq = profile.seq
),

edge_published as (
    select
        line_id,
        seq,
        elevation_ft,
        seq as sample_index
    from {{ ref('elevation') }}
    where line_id != 'AT'
),

published as (
    select * from at_published
    union all
    select * from edge_published
),

dem as (
    select
        line_id,
        sample_index,
        elevation_m
    from {{ ref('stg_derived__dem_samples') }}
)

select
    published.line_id,
    published.seq,
    published.elevation_ft,
    dem.elevation_m
from published
inner join dem
    on
        published.line_id = dem.line_id
        and published.sample_index = dem.sample_index
where (published.elevation_ft is null) != (dem.elevation_m is null)
