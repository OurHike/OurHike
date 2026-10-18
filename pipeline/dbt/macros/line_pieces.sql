{#-
    line_pieces(lines, geom, carried): the rows of `lines` (a CTE or a
    relation) as the pieces a disc-against-line join asks, one row per piece,
    with `carried` (a list of column names) copied onto every piece of its
    line and the piece itself as `piece_5070`.

    Each LineString, and each part of a MultiLineString, is a piece if it has
    at most var `poi_network_ring_part_max_vertices` (1,024) vertices, and
    otherwise is broken into its segments: a two-vertex line from each vertex
    ST_Points gives to the next, a repeated vertex kept (ST_Points keeps
    repeats; trail_line_geometry.sql's line_vertices says where that was
    measured). A disc meets a line exactly when it meets one of the line's
    pieces, so a join that asks "does any line meet this disc" keeps the same
    rows; a join that counts lines must count distinct carried keys, because
    one line can now meet a disc as several pieces.

    Why it exists: on dbt 2.0.6's DuckDB 1.5.4 (spatial 28db190) a spatial
    join of discs against whole lines holds memory per candidate pair, and the
    national network's three longest lines (the Continental Divide Trail's
    704,095- and 402,563-vertex MultiLineStrings, the Pacific Crest Trail's
    265,802-vertex LineString) have bounding boxes thousands of discs fall
    inside. int_points_of_interest__in_corridor's header carries the
    measurement, the failed run it reproduces, and what did not help.
-#}
{% macro line_pieces(lines, geom, carried=[]) -%}
{%- set max_vertices = var('poi_network_ring_part_max_vertices') -%}
{%- set keep -%}
{%- for column in carried %}{{ column }}, {% endfor -%}
{%- endset -%}
select
    {{ keep }}part_geom as piece_5070
from (
    select
        {{ keep }}struct_extract(part, 'geom') as part_geom,
        st_npoints(struct_extract(part, 'geom')) as vertex_count
    from (
        select
            {{ keep }}unnest(st_dump({{ geom }})) as part
        from {{ lines }}
    ) as dumped
) as parts
where vertex_count <= {{ max_vertices }}
union all
select
    {{ keep }}st_makeline(segment_start, segment_end) as piece_5070
from (
    select
        {{ keep }}unnest(list_slice(vertices, 1, -2)) as segment_start,
        unnest(list_slice(vertices, 2, -1)) as segment_end
    from (
        select
            {{ keep }}list_transform(
                st_dump(st_points(struct_extract(part, 'geom'))),
                lambda vertex: struct_extract(vertex, 'geom')
            ) as vertices
        from (
            select
                {{ keep }}unnest(st_dump({{ geom }})) as part
            from {{ lines }}
        ) as dumped
        where st_npoints(struct_extract(part, 'geom')) > {{ max_vertices }}
    ) as long_parts
) as pairs
{%- endmacro %}
