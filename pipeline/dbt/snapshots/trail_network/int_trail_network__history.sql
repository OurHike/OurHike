{% snapshot int_trail_network__history %}
-- The trail network mart's row history (macros/row_history.sql).
--
-- KEYED PARTLY BY POSITION. edge_id is `<part_id>.<piece_index>`
-- (int_trail_network__edges): a part split differently, because a
-- junction appeared on it, gives the same ids different pieces. The
-- history reads that as edits to those edges and as the removal or
-- addition of the last ones, not as a new edge (Reasoned from the
-- derivation; not measured on real data).
--
-- `edge_index`, the row's place in trail_graph.json's `edges`, is left out of
-- the hash: a row added or removed above another moves that place and nothing
-- else about it. row_history_refresh() keeps the current version's place
-- current. `from_node` and `to_node` are places too, in trail_graph.json's
-- `nodes`, and are still hashed, so a node added ahead of an edge's ends
-- still dates the edge as changed (Reasoned from int_trail_network__raw_edges,
-- which numbers nodes in the order they are first reached; not measured, and
-- not decided here).
{{ config(unique_key='edge_id') }}
{{ row_history_snapshot('int_trail_network__final', skip=['edge_index']) }}
{% endsnapshot %}
