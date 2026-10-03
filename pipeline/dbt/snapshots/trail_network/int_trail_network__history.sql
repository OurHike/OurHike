{% snapshot int_trail_network__history %}
-- The trail network mart's row history (macros/row_history.sql).
--
-- KEYED PARTLY BY POSITION. edge_id is `<part_id>.<piece_index>`
-- (int_trail_network__edges): a part split differently, because a
-- junction appeared on it, gives the same ids different pieces. The
-- history reads that as edits to those edges and as the removal or
-- addition of the last ones, not as a new edge (Reasoned from the
-- derivation; not measured on real data).
{{ config(unique_key='edge_id') }}
{{ row_history_snapshot('int_trail_network__final') }}
{% endsnapshot %}
