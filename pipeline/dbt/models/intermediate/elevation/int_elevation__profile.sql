{{ config(materialized='table') }}
-- The A.T. elevation profile as elevation_profile.json publishes it: one row
-- per published sample, in order along the trail. The SQL form of the loop
-- at the end of export_elevation.build_profile (now
-- export_elevation.profile_records), applied to every sample of
-- int_elevation__sample_points with the DEM's answer at its point from
-- stg_derived__dem_samples. Three rules of pipeline/ELT.md's ledger, in the
-- loop's order:
--
-- EL07, THE FIRST PIECE TO REACH A MILE KEEPS IT. Where two pieces cover the
-- same stretch (duplicate geometry surviving the merge, ORDERING.md's
-- degree-6 nodes, about 5 mi of the real trail), their calibrated miles
-- overlap, and publishing both would put those miles on the axis twice and
-- their climb in the total twice. A sample is kept only when its published
-- mile is past every mile before it in the walk: the Python's high-water
-- mark, which only a kept sample raises, so it is the running maximum of
-- every earlier sample's mile. Compared on the rounded mile, as the Python
-- compares, because two samples from different pieces can round to one
-- mile at a seam (two such pairs in 138,710 samples on the run that found
-- it), and keeping both would publish one mile twice. So distance_mi is
-- strictly increasing by construction.
--
-- EL08, part_start AT EACH SEAM: true on the first kept sample of each
-- piece, the very first sample included (#559). The step into it is a seam
-- in the trail rather than a slope: summing such steps put about 36,800 ft
-- of climbing nobody did into the published total before #559.
--
-- EL09, A DEM GAP IS NULL, NEVER 0. A sample the DEM has no answer for keeps
-- its place on the distance axis with no elevation, so a chart's axis stays
-- continuous and nothing counts a climb across the gap. Feet are the DEM's
-- metres over elevation_metres_per_foot, rounded to one decimal as Python's
-- round() rounds (the double's exact value, ties to even): printf('%.1f'),
-- which agreed with it on all of 1,280,000 values where DuckDB's own round()
-- disagreed on 52,559 (measured 2026-10-02 on DuckDB 1.5.5;
-- int_elevation__sample_points has the three-decimal half of that run).
--
-- A SAMPLE THE DEM WAS NOT READ FOR HAS NO ELEVATION HERE, whatever the
-- step's table holds: the join below needs the line, the sample and the point
-- itself to match, so a row from an earlier walk cannot lend a sample its
-- elevation, and `dem_read` says which samples found their row.
-- assert_every_elevation_sample_was_read_at_its_own_point fails the build on
-- any sample that did not, before the mart is read.
--
-- The published numbers are text (distance_mi_text, elevation_ft_text) so a
-- unit test holds them exactly; the elevation mart casts them to decimals.
with points as (
    select * from {{ ref('int_elevation__sample_points') }}
),

dem as (
    select * from {{ ref('stg_derived__dem_samples') }}
),

-- The profile is ATC's centerline on ATC's half-mile mile scale, so its rows
-- carry the newest load of the two layers it is built from.
loads as (
    select max(loaded_at) as loaded_at
    from (
        select loaded_at from {{ ref('stg_atc__centerline_segments') }}
        union all
        select loaded_at from {{ ref('stg_atc__half_mile_markers') }}
    )
),

read_at as (
    select
        points.line_id,
        points.sample_index,
        points.piece_id,
        points.distance_mi_text,
        cast(points.distance_mi_text as decimal(8, 3)) as distance_mi,
        dem.sample_index is not null as dem_read,
        dem.elevation_m
    from points
    left join dem
        on
            points.line_id = dem.line_id
            and points.sample_index = dem.sample_index
            and points.lon = dem.lon
            and points.lat = dem.lat
),

clipped as (
    select
        *,
        coalesce(
            distance_mi > max(distance_mi) over (
                partition by line_id
                order by sample_index
                rows between unbounded preceding and 1 preceding
            ),
            true
        ) as kept
    from read_at
),

kept as (
    select
        *,
        cast(
            row_number() over (partition by line_id order by sample_index) - 1
            as integer
        ) as seq,
        coalesce(
            lag(piece_id) over (partition by line_id order by sample_index)
            != piece_id,
            true
        ) as part_start
    from clipped
    where kept
)

select
    kept.line_id,
    kept.seq,
    kept.sample_index,
    kept.piece_id,
    kept.distance_mi_text,
    case
        when kept.elevation_m is not null
            then
                printf(
                    '%.1f',
                    kept.elevation_m
                    / cast('{{ var("elevation_metres_per_foot") }}' as double)
                )
    end as elevation_ft_text,
    kept.part_start,
    kept.dem_read,
    -- The folder that extracts the centerline, and its registry key.
    'atc' as club,
    'centerline' as source_key,
    loads.loaded_at as _loaded_at
from kept
cross join loads
