-- A published elevation is null exactly where the DEM had no answer at the
-- sample, so a gap reaches the phone as unknown and never as 0 ft (pipeline/
-- ELT.md's safety table: "Null means no DEM coverage, never 0"). A 0 for a
-- gap would draw a cliff into the ribbon and count its climb into the
-- hiker's total; the phone reads a null as a break in the run instead
-- (client/src/lib/elevationProfile.ts). Read through int_elevation__profile,
-- which carries each published sample's place in the walk. Returns no rows.
with published as (
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
