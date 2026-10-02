{{ config(materialized='table') }}
{%- set at_sources = var('trail_network_at_sources') %}
-- The trail lines a route may run on, one row per line part, and one row per
-- refusal: build_trail_graph.py's routable_lines() over the collection
-- build() merges (TN01-TN03 of pipeline/ELT.md's ledger).
--
-- THE INPUT is the trail_lines mart, the lines a phone draws, read as
-- build_trail_graph.py reads the two files written from it: every network
-- line (nearby_trails.geojson, in its feature order), then the A.T.'s
-- centerline and side trails WHOLE (trails.geojson, in its order, kept to
-- the sources in trail_network_at_sources, load_at_lines()' AT_GRAPH_SOURCES).
-- The A.T. is absent from the network half by design (the route owner's
-- line wins, TL11), so without its own lines a graph would refuse a tap on
-- the widest line on the map with a sentence that is false there;
-- assert_the_at_routes_on_the_junction_graph says so loudly, as main()'s
-- WARNING does.
--
-- WHAT IS REFUSED, AND COUNTED rather than dropped silently, in
-- routable_lines()' order:
-- - a line whose trail_status, stripped and lower-cased, reads 'closed':
--   never an edge, so no route runs down a trail its steward closed or a
--   section inside one of NYS Parks' closed areas
--   (int_trail_lines__network_area_closures). It stays drawn;
-- - a line with no geometry, or an empty one ('empty'), or one that is not
--   a LineString or MultiLineString ('not_a_line');
-- - each part of a line that is empty or has fewer than two coordinates
--   ('empty', one row per part).
-- Every other part of every other line is routable, a MultiLineString's
-- parts each on their own, in order.
--
-- `part_order` is the part's place in routable_lines()' list, which is the
-- order every later model and step_node_lines reads the parts in. Geometry
-- is WKT text in lon/lat (a 2.0.6 unit test cannot hold a GEOMETRY), every
-- vertex the mart's double, read back exactly.
with lines as (
    select
        trail_line_id,
        club,
        source_key,
        _loaded_at,
        name,
        blaze_color,
        trail_status,
        geom_geojson,
        line_kind != 'network' as is_at,
        feature_order
    from {{ ref('trail_lines') }}
    where
        line_kind = 'network'
        or source_key in (
            {%- for source in at_sources %}
            '{{ source }}'{{ "," if not loop.last }}
            {%- endfor %}
        )
),

judged as (
    select
        *,
        row_number() over (order by is_at, feature_order) - 1 as line_order,
        st_geomfromgeojson(geom_geojson) as geom,
        case
            when
                lower(coalesce({{ python_strip('trail_status') }}, ''))
                = 'closed'
                then 'closed'
            when geom_geojson is null then 'empty'
            when st_isempty(st_geomfromgeojson(geom_geojson)) then 'empty'
            when
                st_geometrytype(st_geomfromgeojson(geom_geojson))
                not in ('LINESTRING', 'MULTILINESTRING')
                then 'not_a_line'
        end as line_refused_because
    from lines
),

parts as (
    select
        *,
        unnest(
            list_transform(
                st_dump(geom), lambda piece: struct_extract(piece, 'geom')
            )
        ) as part,
        generate_subscripts(st_dump(geom), 1) as part_index
    from judged
    where line_refused_because is null
),

judged_parts as (
    select
        *,
        case
            when st_isempty(part) or st_npoints(part) < 2 then 'empty'
        end as refused_because
    from parts
),

routable as (
    select
        trail_line_id || '#' || part_index as part_id,
        row_number() over (order by line_order, part_index) - 1 as part_order,
        line_order,
        part_index,
        trail_line_id as trail_id,
        source_key,
        club,
        _loaded_at,
        name,
        blaze_color,
        is_at,
        cast(null as varchar) as refused_because,
        st_astext(part) as geom_wkt
    from judged_parts
    where refused_because is null
),

refused_parts as (
    select
        trail_line_id || '#' || part_index as part_id,
        cast(null as bigint) as part_order,
        line_order,
        part_index,
        trail_line_id as trail_id,
        source_key,
        club,
        _loaded_at,
        name,
        blaze_color,
        is_at,
        refused_because,
        cast(null as varchar) as geom_wkt
    from judged_parts
    where refused_because is not null
),

refused_lines as (
    select
        trail_line_id || '#' as part_id,
        cast(null as bigint) as part_order,
        line_order,
        cast(null as bigint) as part_index,
        trail_line_id as trail_id,
        source_key,
        club,
        _loaded_at,
        name,
        blaze_color,
        is_at,
        line_refused_because as refused_because,
        cast(null as varchar) as geom_wkt
    from judged
    where line_refused_because is not null
)

select * from routable
union all
select * from refused_parts
union all
select * from refused_lines
