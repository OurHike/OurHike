-- The junction graph's pieces and landings: step_node_lines's table
-- (pipeline/step_node_lines.py), staged like any table a source lands.
-- int_trail_network__node_lookups reads both kinds: each piece's two ends
-- and each landing are where build_trail_graph.py asks its node grid for a
-- node.
with source as (
    -- The step writes geometry as GeoJSON text in EPSG:5070 metres; cast
    -- here, as decision 40 has staging do. No CRS is set: these are metres,
    -- and only int_trail_network__ models, which know it, read them.
    select
        * exclude (geometry),
        st_geomfromgeojson(cast(geometry as varchar)) as geom
    from {{ source('derived', 'graph_pieces') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key([
            "'graph_pieces'",
            'row_kind',
            'part_id',
            'piece_index',
            'cut_key',
        ]) }} as graph_piece_key,
        row_kind,
        part_id,
        piece_index,
        piece_rank,
        weld_rank,
        cut_key,
        geom,
        _loaded_at as loaded_at
    from source
)

{{ dbt_utils.deduplicate(
    relation='renamed', partition_by='graph_piece_key', order_by='graph_piece_key'
) }}
