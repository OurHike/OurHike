{{ config(materialized='table') }}
{%- set tolerance_m = var('trail_lines_network_duplicate_tolerance_m') %}
{#- Two names whose copies run within a centimetre of the same length tie
    (S2, below). Reasoned, not fitted: the 16-segment buffer misses up to
    10 m x (1 - cos(pi/64)) = 12 mm of a true circle at a line's ends, and a
    published vertex is cut to 6 decimals of a degree, about 0.1 m, so no
    difference under a centimetre is the ground's. Any value from about
    1e-6 m, where two copies drawn the same length differ by arithmetic,
    up to that 0.1 m answers the same. #}
{%- set name_tie_m = 0.01 %}
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
-- INHERITABLE), and names the junior's source in `duplicate_of`. Both
-- constants round toward missing a duplicate, and are chosen rather than
-- fitted: measured for New York City's pair only (#1453 — Measure whether
-- New York City's two registered layers draw the same tread twice — 2,095
-- greenway segments sit on NYC Parks ground), @unvalidated for any other
-- pair until its overlap is measured.
--
-- A SENIOR WITH NO NAME TAKES THE NAME IT FOLLOWS LONGEST: standard S2, the
-- maintainer's poll of 2026-10-11 ("the named copy it follows for the
-- longest distance (within 10 m), not the first in file order or by key").
-- Of the names its swallowed copies carry, it takes the one whose copies lie
-- within 10 m of it along the greatest length, each name's copies unioned
-- first, so ground that two copies of one name share (one in each of two
-- layers) counts once. Only a copy it swallows counts: a named path beside
-- it that is kept as a line of its own is not a copy, and the line does not
-- take its name. Two names within `name_tie_m`, 1 cm, of the same length tie,
-- and the name that sorts first as text (DuckDB's byte order) wins, so copies
-- drawn the same length name the line the same way on every build. Today's
-- exporter takes the first named copy in file order (lib/duplicates.py:
-- apply_duplicates() merges in file order and merge() keeps the first name),
-- and this model took the first by staging key until S2.
-- Measured 2026-10-11 on NYC Open Data's live rows (vjbm-hsyr, inkn-q76z,
-- mzxg-pwib), counting every segment of each name within 10 m, in UTM 18N:
-- Brookfield Park's unnamed line (121 m) has BROOKFIELD PARK WEST OUTER LOOP
-- along 140 m and BROOKFIELD PARK BLUE TRAIL along 26 m; Cunningham Park's
-- (244 m) has VANDERBILT MOTOR PARKWAY along 154 m and CUNNINGHAM PARK
-- GREENWAY along 109 m. Counting only the copies each swallows, as this model
-- does, in EPSG:5070: 130 m against 25 m (two segments) and 146 m against
-- 100 m (five), the counts monthly run 30's rebuild found; which segments
-- they are is Reasoned from each one's share of its length inside that
-- line's buffer. Both ways name them West Outer Loop and Vanderbilt Motor
-- Parkway, where today's exporter names Cunningham Park's line Cunningham
-- Park Greenway. `trail_status` and `blaze_color` still come from the first
-- junior that has one, in pair order then staging-key order: S2 names the
-- name alone.
--
-- ONE PAIR AT A TIME IN THE PYTHON, ALL AT ONCE HERE. deduplicate() applies
-- the pairs in registry order against the lines still standing, which only
-- matters when a source is junior in one pair and senior in another. No such
-- chain is declared, and this model's test stops the build if one is, rather
-- than answering it differently. Where one senior line swallows lines from
-- two pairs, `duplicate_of` names the later pair's junior, as the Python's
-- last merge() does; within a pair the juniors give `trail_status` and
-- `blaze_color` in staging-key order, where the Python merges them in file
-- order.
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
        judged.published_id,
        judged.name,
        judged.trail_status,
        judged.trail_status_basis,
        judged.closure_kind,
        blazes.blaze_color,
        st_geomfromtext(judged.geom_wkt) as geom,
        st_transform(
            st_geomfromtext(judged.geom_wkt),
            'EPSG:4326',
            'EPSG:5070',
            always_xy := true
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
            and st_dwithin(
                junior.geom_m,
                senior.geom_m,
                {{ tolerance_m }}
            )
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
                st_buffer(
                    st_union_agg(senior_m),
                    {{ tolerance_m }},
                    16
                )
            )
        ) / st_length(any_value(junior_m)) as junior_share
    from candidates
    group by junior_key
),

-- The length of each junior lying inside one senior line's own 10 m buffer.
followed as (
    select
        junior_key,
        junior_m,
        senior_key,
        senior_id,
        senior_m,
        st_length(
            st_intersection(
                junior_m,
                st_buffer(senior_m, {{ tolerance_m }}, 16)
            )
        ) as followed_m
    from candidates
),

-- The senior line each duplicate is reported against: most of the junior
-- inside its own buffer, the lower id on a tie (find_duplicates()' `best`).
reported as (
    select
        followed.junior_key,
        followed.junior_m,
        followed.senior_key,
        followed.senior_m
    from followed
    inner join shares on followed.junior_key = shares.junior_key
    where
        shares.junior_share
        >= {{ var('trail_lines_network_duplicate_min_share') }}
    qualify
        row_number() over (
            partition by followed.junior_key
            order by followed.followed_m desc, followed.senior_id asc
        ) = 1
),

-- Each swallowed junior with what merge() may copy from it, in merge order:
-- pair order, then staging-key order.
swallowed as (
    select
        reported.senior_key,
        reported.senior_m,
        reported.junior_m,
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

-- S2 (the header): how far each name's swallowed copies follow their senior,
-- the copies of one name unioned first so shared ground counts once.
name_lengths as (
    select
        senior_key,
        name,
        st_length(
            st_intersection(
                st_union_agg(junior_m),
                st_buffer(any_value(senior_m), {{ tolerance_m }}, 16)
            )
        ) as followed_m
    from swallowed
    where coalesce(name, '') != ''
    group by senior_key, name
),

name_ties as (
    select
        senior_key,
        name,
        followed_m
        >= max(followed_m) over (partition by senior_key)
        - {{ name_tie_m }} as ties_the_longest
    from name_lengths
),

-- The name followed longest; of names tied with it, the one sorting first.
longest_name as (
    select
        senior_key,
        name as junior_name
    from name_ties
    where ties_the_longest
    qualify row_number() over (partition by senior_key order by name) = 1
),

-- merge(), field by field: a senior's own value wins where it has one, else
-- the first junior's that has one; `duplicate_of` is the last junior's.
inherited as (
    select
        senior_key,
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
    lines.published_id,
    case
        when coalesce(lines.name, '') = ''
            then coalesce(longest_name.junior_name, lines.name)
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
    -- WKT, as int_trail_lines__network_judged carries it and for its reason.
    st_astext(lines.geom) as geom_wkt,
    lines._loaded_at
from lines
left join inherited on lines.trail_segment_key = inherited.senior_key
left join longest_name on lines.trail_segment_key = longest_name.senior_key
left join reported on lines.trail_segment_key = reported.junior_key
where reported.junior_key is null
