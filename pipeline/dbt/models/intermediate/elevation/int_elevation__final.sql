-- int_elevation__final: the elevation mart's rows before their row dates, every
-- contracted column but _first_seen_at and _changed_at. This is what
-- models/marts/elevation/elevation.sql held until decision 57;
-- int_elevation__history snapshots it, and the mart reads that snapshot.
--
-- The elevation mart: one sample per row on a profiled line, keyed by
-- (line_id, seq), with the safety fields of pipeline/ELT.md's table ("The
-- eleven marts"). Two kinds of line:
--
-- - the A.T. ('AT'), from int_elevation__profile, a sample every 25 m on
--   ATC's own mile scale; elevation_profile.json is written from these rows
--   (pub_elevation_profile);
-- - each junction-graph edge (its edge_id), from int_elevation__edge_samples,
--   both ends and about every 25 m between; trail_graph_profile.json is
--   written from these rows (pub_trail_graph_profile).
--
-- elevation_ft is the elevation each file publishes, at the precision it
-- publishes it: tenths of a foot on the A.T. (export_elevation.py:1420),
-- whole feet on an edge (export_network_profile.edge_profile), each rounded
-- once from the DEM's own metres, which elevation_m keeps beside it so
-- nothing downstream has to round a rounded number again. Both are null
-- where the DEM has no answer, never 0, and a test holds them to the DEM
-- step's own nulls. distance_mi is the A.T.'s mile, strictly increasing; an
-- edge has no mile axis and carries none, as trail_graph_profile.json
-- publishes none. part_start is true at each seam: each centerline piece's
-- first sample on the A.T., and each edge's first sample, an edge being one
-- piece.
--
-- Only rows whose sources may publish (int_sources__publication,
-- pipeline/ELT.md "Who may publish"). The A.T. profile is ATC's centerline on
-- ATC's half-mile mile scale, so it needs both sources; an edge needs its
-- own line's source. A source the registry does not list may not publish.
with profile as (
    select * from {{ ref('int_elevation__profile') }}
),

edge_samples as (
    select * from {{ ref('int_elevation__edge_samples') }}
),

edges as (
    select
        edge_id,
        club,
        source_key,
        _loaded_at
    from {{ ref('int_trail_network__edges') }}
),

publication as (
    select * from {{ ref('int_sources__publication') }}
),

mile_scale as (
    select may_publish
    from publication
    where source_key = 'half_mile_points_from_springer'
),

at_samples as (
    select
        profile.line_id,
        profile.seq,
        cast(profile.distance_mi_text as decimal(8, 3)) as distance_mi,
        cast(profile.elevation_ft_text as decimal(6, 1)) as elevation_ft,
        profile.elevation_m,
        profile.part_start,
        profile.club,
        profile.source_key,
        profile._loaded_at
    from profile
    inner join publication on profile.source_key = publication.source_key
    cross join mile_scale
    where publication.may_publish and mile_scale.may_publish
),

network_samples as (
    select
        edge_samples.edge_id as line_id,
        edge_samples.sample_index as seq,
        cast(null as decimal(8, 3)) as distance_mi,
        cast(edge_samples.elevation_ft as decimal(6, 1)) as elevation_ft,
        edge_samples.elevation_m,
        edge_samples.sample_index = 0 as part_start,
        edges.club,
        edges.source_key,
        edges._loaded_at
    from edge_samples
    inner join edges on edge_samples.edge_id = edges.edge_id
    inner join publication on edges.source_key = publication.source_key
    where publication.may_publish
)

select * from at_samples
union all
select * from network_samples
