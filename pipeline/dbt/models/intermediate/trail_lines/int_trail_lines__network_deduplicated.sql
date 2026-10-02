{{ config(materialized='table') }}
-- The network's published lines: every row int_trail_lines__network_judged
-- keeps whose source may publish, with each declared duplicate drawn once
-- (TL18, lib/duplicates.py, #1459 — Two New York City agencies draw the same
-- tread and the map draws both lines, because nothing dedupes geometry
-- across sources), and every line's blaze from int_trail_lines__blazes.
--
-- PUBLICATION RUNS FIRST (pipeline/ELT.md, "Publication filters run before
-- dedup"): a row whose source may not publish is gone before any line is
-- compared, so it can never swallow a line that ships and then vanish with
-- it. A junior whose senior may not publish is therefore compared with
-- nothing and keeps every line, which is declared_duplicate_pairs()'s own
-- rule for a senior that is not shipping. Today's export compares every
-- source and lets publish.py hold the whole file back when any source is
-- held back; here a held-back source's lines are simply absent.
--
-- THE RULE, find_duplicates() and merge() in SQL, every distance in
-- EPSG:5070 metres (always_xy, pipeline/ELT.md's "Metres are measured in
-- EPSG:5070"). A junior line of positive length with a senior line within
-- DUPLICATE_TOLERANCE_M, 10 m, is a duplicate when at least
-- DUPLICATE_MIN_SHARE, 0.5, of its length lies inside the 10 m buffer of the
-- union of those senior lines; it is reported against the senior line whose
-- own 10 m buffer holds most of it, the lower id winning a tie. Buffers use
-- 16 segments per quarter circle, shapely's `.buffer()` default. The
-- duplicate is removed; its senior keeps its own geometry and fills `name`,
-- `trail_status` and `blaze_color` only where it has none (merge()'s
-- INHERITABLE, the first junior to have one winning), and names the
-- junior's source in `duplicate_of`. Both constants round toward missing a
-- duplicate, and are chosen rather than fitted: measured for New York City's
-- pair only (#1453 — Measure whether New York City's two registered layers
-- draw the same tread twice — 2,095 greenway segments sit on NYC Parks
-- ground), @unvalidated for any other pair until its overlap is measured.
--
-- ONE PAIR AT A TIME IN THE PYTHON, ALL AT ONCE HERE. deduplicate() applies
-- the pairs in registry order against the lines still standing, which only
-- matters when a source is junior in one pair and senior in another. No such
-- chain is declared, and this model's test stops the build if one is, rather
-- than answering it differently. Where one senior line swallows lines from
-- two pairs, `duplicate_of` names the later pair's junior, as the Python's
-- last merge() does; within a pair the juniors merge in staging-key order,
-- where the Python merges them in file order.
with judged as (
    select * from {{ ref('int_trail_lines__network_judged') }}
),

blazes as (
    select * from {{ ref('int_trail_lines__blazes') }}
),

lines as (
    select
        judged.trail_segment_key,
        judged.source_key,
        judged.club,
        judged.file_row,
        judged.duplicate_of as senior_source,
        judged.trail_line_id,
        judged.name,
        judged.trail_status,
        judged.trail_status_basis,
        judged.closure_kind,
        blazes.blaze_color,
        judged.geom,
        st_transform(
            judged.geom, 'EPSG:4326', 'EPSG:5070', always_xy := true
        ) as geom_m,
        judged._loaded_at
    from judged
    inner join blazes on judged.trail_segment_key = blazes.trail_segment_key
    where judged.dropped_because is null and judged.may_publish
),

-- declared_duplicate_pairs(): (senior, junior) for each source whose entry
-- names a `duplicate_of`, in the junior's registry order.
pairs as (
    select distinct
        senior_source,
        source_key as junior_source,
        file_row as pair_order
    from lines
    where senior_source is not null
),

-- Each junior line against every senior line of its pair within 10 m.
candidates as (
    select
        junior.trail_segment_key as junior_key,
        junior.trail_line_id as junior_id,
        junior.source_key as junior_source,
        pairs.pair_order,
        junior.geom_m as junior_m,
        senior.trail_segment_key as senior_key,
        senior.trail_line_id as senior_id,
        senior.geom_m as senior_m
    from lines as junior
    inner join pairs on junior.source_key = pairs.junior_source
    inner join lines as senior
        on
            pairs.senior_source = senior.source_key
            and st_dwithin(junior.geom_m, senior.geom_m, 10.0)
    where st_length(junior.geom_m) > 0
),

shares as (
    select
        junior_key,
        any_value(junior_id) as junior_id,
        any_value(junior_source) as junior_source,
        any_value(pair_order) as pair_order,
        st_length(
            st_intersection(
                any_value(junior_m),
                st_buffer(st_union_agg(senior_m), 10.0, 16)
            )
        ) / st_length(any_value(junior_m)) as junior_share
    from candidates
    group by junior_key
),

-- The senior line each duplicate is reported against: most of the junior
-- inside its own buffer, the lower id on a tie (find_duplicates()' `best`).
reported as (
    select
        candidates.junior_key,
        candidates.senior_key
    from candidates
    inner join shares on candidates.junior_key = shares.junior_key
    where shares.junior_share >= 0.5
    qualify
        row_number() over (
            partition by candidates.junior_key
            order by
                st_length(
                    st_intersection(
                        candidates.junior_m,
                        st_buffer(candidates.senior_m, 10.0, 16)
                    )
                ) desc,
                candidates.senior_id asc
        ) = 1
),

-- Each swallowed junior with what merge() may copy from it, in merge order:
-- pair order, then staging-key order.
swallowed as (
    select
        reported.senior_key,
        shares.pair_order,
        lines.trail_segment_key,
        lines.source_key,
        lines.name,
        lines.trail_status,
        lines.blaze_color
    from reported
    inner join shares on reported.junior_key = shares.junior_key
    inner join lines on reported.junior_key = lines.trail_segment_key
),

-- merge(), field by field: a senior's own value wins where it has one, else
-- the first junior's that has one; `duplicate_of` is the last junior's.
inherited as (
    select
        senior_key,
        list_extract(
            list(name order by pair_order, trail_segment_key) filter (
                where coalesce(name, '') != ''
            ),
            1
        ) as junior_name,
        list_extract(
            list(trail_status order by pair_order, trail_segment_key) filter (
                where coalesce(trail_status, '') != ''
            ),
            1
        ) as junior_status,
        list_extract(
            list(blaze_color order by pair_order, trail_segment_key) filter (
                where coalesce(blaze_color, '') != ''
            ),
            1
        ) as junior_blaze,
        list_extract(
            list(source_key order by pair_order, trail_segment_key), -1
        ) as swallowed_source
    from swallowed
    group by senior_key
)

select
    lines.trail_segment_key,
    lines.source_key,
    lines.club,
    lines.file_row,
    lines.trail_line_id,
    case
        when coalesce(lines.name, '') = ''
            then coalesce(inherited.junior_name, lines.name)
        else lines.name
    end as name,
    case
        when coalesce(lines.trail_status, '') = ''
            then coalesce(inherited.junior_status, lines.trail_status)
        else lines.trail_status
    end as trail_status,
    lines.trail_status_basis,
    lines.closure_kind,
    case
        when coalesce(lines.blaze_color, '') = ''
            then coalesce(inherited.junior_blaze, lines.blaze_color)
        else lines.blaze_color
    end as blaze_color,
    inherited.swallowed_source as duplicate_of,
    lines.geom,
    lines._loaded_at
from lines
left join inherited on lines.trail_segment_key = inherited.senior_key
left join reported on lines.trail_segment_key = reported.junior_key
where reported.junior_key is null
