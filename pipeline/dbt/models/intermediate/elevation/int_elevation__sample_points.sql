{{ config(materialized='table') }}
-- Where the A.T. elevation profile reads the DEM: one row per 25 m sample
-- along the mile axis, in the order the walk meets them, with the published
-- mile of each. EL05 of pipeline/ELT.md's ledger, the SQL form of
-- export_elevation.sample_points_along_parts and the mile half of
-- build_profile's loop. step_dem_sampling (pipeline/step_dem_sampling.py)
-- reads every row of this model and writes the DEM's answer at each point to
-- derived.dem_samples; int_elevation__profile joins the two.
--
-- THE WALK, as the Python takes it. The pieces of int_trail_lines__mile_axis
-- in mile order (piece_id), each in EPSG:5070 metres and oriented so the mile
-- grows. A sample every elevation_sample_interval_m (25) of cumulative
-- distance: the first sample of a piece sits at what the previous piece left
-- over, so the interval runs straight across the gap between two pieces as
-- if they touched (the Python's docstring, point 4: "a bounded approximation
-- worth naming plainly"). A piece shorter than the carry gets no sample and
-- passes the rest of the carry on. Every sample is kept here, including the
-- ones int_elevation__profile drops where two pieces cover the same miles,
-- because export_elevation.py reads the DEM at those too and the DEM step
-- must ask the same questions in the same order to get the same answers.
--
-- TO THE BIT WHERE IT IS CHEAP, and the two places it is not, measured
-- 2026-10-02 against export_elevation.py on ATC's live centerline (3,025
-- segments) and half-mile markers (4,395), read that day, on Python's DuckDB
-- 1.5.5 with int_trail_lines__mile_axis built from the same files:
-- - the same 139,218 samples, on the same pieces, at the same along- and
--   walk distances to the bit. That needs the Python's own arithmetic: each
--   along-distance is the previous one plus 25 (a repeated sum, which rounds
--   differently from carry + 25 * k), and each piece's offset is the running
--   sum of the lengths before it, added in piece order. Both are recursive
--   CTEs below, because DuckDB's window sum adds in its own order (345 of the
--   562 pieces' running vertex sums came out different in the last bit);
-- - the same three-decimal mile on all 139,218 (the unrounded mile differs on
--   168, by at most 4.5e-13 mi, from the axis's anchor along-distances,
--   which int_trail_lines__mile_axis_markers says differ by up to 1.42e-14
--   mi);
-- - the point itself differs on 91 samples, by at most 4.7e-10 m, and its
--   lon/lat on 24, by at most 3.6e-14 degrees: st_lineinterpolatepoint takes
--   a fraction of the length where shapely's interpolate takes the length.
--   A DEM pixel is about 10 m, so such a point can only read a different
--   pixel when it lies within about 1e-9 m of a pixel edge (Reasoned).
--   Replicating shapely's walk along the vertices exactly would need a
--   running sum over up to 48,072 vertices a piece, in vertex order, which
--   this file's two recursive CTEs could only do one vertex per iteration.
-- Through dbt 2.0.6's DuckDB 1.5.4, on the same files and a synthetic DEM,
-- the whole chain wrote an elevation_profile.json identical to
-- export_elevation.py's apart from one trailing newline: 138,697 samples
-- (pub_elevation_profile has the run). This model took 51 s of that 75 s
-- build, each st_lineinterpolatepoint walking its piece from the start.
--
-- THE MILE is export_elevation's: the distance along the piece, taken as the
-- walk distance minus the piece's offset as the Python takes it, in miles,
-- through the piece's anchors (macros/mile_at_along.sql, which is
-- CalibratedPart.mile_at). The samples are positions along the pieces, so no
-- nearest-piece search is needed: each sample's piece is the one the walk is
-- on. distance_mi_text is that mile rounded to three
-- decimals as Python's round() rounds: the double's exact value, ties to
-- even. That is printf('%.3f'), which agreed with Python's round on all of
-- 1,280,000 values, near-ties and exact binary ties included, where DuckDB's
-- own round() disagreed on 112,122 of them (measured 2026-10-02 on DuckDB
-- 1.5.5). It is text so a unit test holds it exactly, and
-- int_elevation__profile casts it.
with recursive pieces as (
    select
        piece_id,
        geom_5070,
        length_m,
        anchor_along_mi,
        anchor_mile,
        cast('{{ var("elevation_sample_interval_m") }}' as double)
            as interval_m
    from {{ ref('int_trail_lines__mile_axis') }}
),

last_piece as (
    select max(piece_id) as piece_id from pieces
),

-- One row per piece: the along-distance of its first sample (the carry from
-- the piece before) and its offset, the sum of every earlier piece's length.
-- The carry out of a piece is the first along-distance past its length,
-- reached by adding the interval as the Python's while loop adds it, less
-- that length. The list only bounds how many additions are tried; the case
-- stops adding once the sum is past the piece.
--
-- The two-parameter lambda is written with DuckDB's arrow, which DuckDB
-- 1.3 deprecated, because SQLFluff 4.3.0 cannot parse `lambda a, b:`
-- (measured 2026-10-02: it parses the arrow and a one-parameter lambda).
-- DuckDB 1.5.4 and 1.5.5 run it with lambda_syntax at its DEFAULT; a
-- DuckDB that removes the arrow fails this model loudly at the bump.
walked (piece_id, first_along_m, offset_m) as (
    select
        0,
        cast(0.0 as double),
        cast(0.0 as double)
    union all
    select
        walked.piece_id + 1,
        list_reduce(
            range(
                cast(
                    greatest(
                        floor(
                            (pieces.length_m - walked.first_along_m)
                            / pieces.interval_m
                        ),
                        0
                    ) as bigint
                ) + 2
            ),
            (along_m, attempt) -> case
                when along_m <= pieces.length_m
                    then along_m + pieces.interval_m
                else along_m
            end,
            walked.first_along_m
        ) - pieces.length_m,
        walked.offset_m + pieces.length_m
    from walked
    inner join pieces on walked.piece_id = pieces.piece_id
    cross join last_piece
    where walked.piece_id < last_piece.piece_id
),

-- Every sample of every piece, the along-distance one interval at a time.
samples (piece_id, step, along_m) as (
    select
        walked.piece_id,
        0,
        walked.first_along_m
    from walked
    inner join pieces on walked.piece_id = pieces.piece_id
    where walked.first_along_m <= pieces.length_m
    union all
    select
        samples.piece_id,
        samples.step + 1,
        samples.along_m + pieces.interval_m
    from samples
    inner join pieces on samples.piece_id = pieces.piece_id
    where samples.along_m + pieces.interval_m <= pieces.length_m
),

located as (
    select
        samples.piece_id,
        samples.step,
        samples.along_m,
        -- build_profile's `distance_m - offsets[part]`: the walk distance,
        -- then the piece's offset back off it, in double as the Python
        -- takes both.
        (
            (walked.offset_m + samples.along_m) - walked.offset_m
        ) / cast('{{ var("mile_axis_metres_per_mile") }}' as double)
            as mile_along_mi,
        pieces.anchor_along_mi,
        pieces.anchor_mile,
        -- A piece of no length has one point to read.
        case
            when pieces.length_m > 0
                then
                    st_lineinterpolatepoint(
                        pieces.geom_5070, samples.along_m / pieces.length_m
                    )
            else st_startpoint(pieces.geom_5070)
        end as point_5070
    from samples
    inner join walked on samples.piece_id = walked.piece_id
    inner join pieces on samples.piece_id = pieces.piece_id
),

miles as (
    select
        piece_id,
        step,
        along_m,
        point_5070,
        {{ mile_at_along('mile_along_mi', 'anchor_along_mi', 'anchor_mile') }}
            as mile
    from located
),

-- export_elevation.reproject_points_to_wgs84: each point back to lon/lat,
-- always_xy, as an st_point of its own coordinates.
placed as (
    select
        piece_id,
        step,
        along_m,
        mile,
        st_transform(
            st_point(st_x(point_5070), st_y(point_5070)),
            'EPSG:5070',
            'EPSG:4326',
            always_xy := true
        ) as point_4326
    from miles
)

select
    -- The A.T., as export_poi.py's TRAIL_ID names it on every POI.
    'AT' as line_id,
    cast(
        row_number() over (order by piece_id, step) - 1 as integer
    ) as sample_index,
    piece_id,
    along_m,
    mile,
    printf('%.3f', mile) as distance_mi_text,
    st_x(point_4326) as lon,
    st_y(point_4326) as lat
from placed
