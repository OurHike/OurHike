-- The elevation mart: one 25 m sample per row on a profiled line, keyed by
-- (line_id, seq), with the safety fields of pipeline/ELT.md's table ("The
-- eleven marts"). Today one line, the A.T., from int_elevation__profile;
-- elevation_profile.json is written from it by pub_elevation_profile.
--
-- elevation_ft is null where the DEM has no answer, never 0, and a test
-- holds it to the DEM step's own nulls. distance_mi is strictly increasing
-- within a line, and part_start is true at each seam. Both numbers arrive as
-- the exact decimal text int_elevation__profile rounded, so the casts here
-- are exact.
--
-- Only rows whose sources may publish (int_sources__publication,
-- pipeline/ELT.md "Who may publish"): the profile is ATC's centerline, so
-- its own source, on ATC's half-mile mile scale, so the markers' source as
-- well. A source the registry does not list may not publish, so either one
-- missing empties the mart rather than publishing it.
with profile as (
    select * from {{ ref('int_elevation__profile') }}
),

publication as (
    select * from {{ ref('int_sources__publication') }}
),

mile_scale as (
    select may_publish
    from publication
    where source_key = 'half_mile_points_from_springer'
)

select
    profile.line_id,
    profile.seq,
    cast(profile.distance_mi_text as decimal(8, 3)) as distance_mi,
    cast(profile.elevation_ft_text as decimal(6, 1)) as elevation_ft,
    profile.part_start,
    profile.club,
    profile.source_key,
    profile._loaded_at
from profile
inner join publication on profile.source_key = publication.source_key
cross join mile_scale
where publication.may_publish and mile_scale.may_publish
