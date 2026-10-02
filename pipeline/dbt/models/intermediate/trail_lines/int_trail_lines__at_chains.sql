{{ config(materialized='table') }}
-- The centerline's published lines, merged into maximal chains (TL16),
-- export_trails.merge_chain_records(): one row per chain,
-- `centerline:chain:<n>`.
--
-- WHY: geojson-vt drops whole features under ~1.4 km at z4, and ATC surveys
-- the centerline in ~1.2 km segments, so unmerged the A.T. drew with
-- miles-long gaps (#160 — Zoomed out, the trail draws with gaps: whole
-- short segments are simplified away; #161 — Export the centerline as
-- merged chains, so per-zoom line simplification can come back on). The
-- client spots the merged shape by the `centerline:chain:` ids, so their
-- spelling is a published contract.
--
-- HOW, in the Python's order: after the 1 m pass, every centerline line's
-- parts, in the layer's order, are collected per (source, blaze_color), so a
-- chain never crosses a blaze boundary, and merged where endpoints touch
-- exactly (ST_LineMerge, shapely's linemerge, both GEOS's LineMerger). The
-- chains are numbered by their bounds, (xmin, ymin, xmax, ymax), so the same
-- input gives the same ids; a tie keeps the merge's own order, as Python's
-- stable sort does. Only the sources in CHAIN_MERGED_SOURCES merge, today
-- the centerline: each side trail is its own destination and stays whole.
--
-- A chain's name is the one name every named segment of its group agrees
-- on, else null: merge_chain_records() decides it per group, so every chain
-- of a group carries the same one.
--
-- `length_m` is the chain's parts' full-resolution lengths summed. The
-- merge only joins whole input lines end to end, so each part of a segment's
-- 1 m line lies in exactly one chain, the one that covers it; the parts of
-- one MultiLineString segment can lie in different chains. The tests hold
-- every part to exactly one chain and every chain to at least one part.
with simplified as (
    select * from {{ ref('int_trail_lines__at_simplified') }}
    where source_key in ('centerline')
),

-- Each segment's parts, with the full-resolution part each came from: the
-- 1 m pass works part by part and the fallback keeps every part, so the two
-- dumps pair up in order.
parts as (
    select
        source_key,
        blaze_color,
        source_order,
        source_row,
        trail_segment_key,
        _loaded_at,
        struct_extract(part, 'path') as part_path,
        struct_extract(part, 'geom') as part_line,
        st_length(
            st_transform(
                struct_extract(full_part, 'geom'),
                'EPSG:4326',
                'EPSG:5070',
                always_xy := true
            )
        ) as full_length_m
    from (
        select
            source_key,
            blaze_color,
            source_order,
            source_row,
            trail_segment_key,
            _loaded_at,
            unnest(st_dump(st_geomfromtext(geom_wkt))) as part,
            unnest(st_dump(st_geomfromtext(full_geom_wkt))) as full_part
        from simplified
    ) as dumped
),

groups as (
    select
        source_key,
        blaze_color,
        min(source_order * 1000000000 + source_row) as group_order,
        st_linemerge(
            st_collect(
                list(part_line order by source_order, source_row, part_path)
            )
        ) as merged
    from parts
    group by source_key, blaze_color
),

group_names as (
    select
        source_key,
        blaze_color,
        case
            when count(distinct name) = 1 then any_value(name)
        end as name
    from simplified
    where coalesce(name, '') != ''
    group by source_key, blaze_color
),

chains as (
    select
        source_key,
        blaze_color,
        group_order,
        merge_order,
        struct_extract(dumped_chain, 'geom') as geom
    from (
        select
            source_key,
            blaze_color,
            group_order,
            unnest(st_dump(merged)) as dumped_chain,
            generate_subscripts(st_dump(merged), 1) as merge_order
        from groups
    ) as dumped
),

numbered as (
    select
        *,
        row_number() over (
            partition by source_key
            order by
                group_order,
                st_xmin(geom),
                st_ymin(geom),
                st_xmax(geom),
                st_ymax(geom),
                merge_order
        ) - 1 as chain_index
    from chains
),

-- Each part, with the chain that covers it.
membership as (
    select
        numbered.source_key,
        numbered.chain_index,
        parts.trail_segment_key,
        parts.full_length_m,
        parts._loaded_at,
        count(*) over (
            partition by parts.trail_segment_key, parts.part_path
        ) as covering_chains
    from parts
    inner join numbered
        on
            parts.source_key = numbered.source_key
            and parts.blaze_color = numbered.blaze_color
            and st_covers(numbered.geom, parts.part_line)
),

totals as (
    select
        source_key,
        chain_index,
        sum(full_length_m) as length_m,
        max(_loaded_at) as _loaded_at,
        count(*) as part_count,
        max(covering_chains) as most_covering_chains
    from membership
    group by source_key, chain_index
)

select
    numbered.source_key || ':chain:' || numbered.chain_index as trail_line_id,
    numbered.source_key,
    'atc' as club,
    numbered.chain_index,
    group_names.name,
    numbered.blaze_color,
    st_astext(numbered.geom) as geom_wkt,
    totals.length_m,
    st_length(
        st_transform(numbered.geom, 'EPSG:4326', 'EPSG:5070', always_xy := true)
    ) as published_length_m,
    totals.part_count,
    totals.most_covering_chains,
    totals._loaded_at
from numbered
left join group_names
    on
        numbered.source_key = group_names.source_key
        and numbered.blaze_color = group_names.blaze_color
left join totals
    on
        numbered.source_key = totals.source_key
        and numbered.chain_index = totals.chain_index
