{% snapshot int_trail_lines__history %}
-- The trail lines mart's row history (macros/row_history.sql).
--
-- KEYED PARTLY BY POSITION. An A.T. line's trail_line_id is
-- `<source>:chain:<chain_index>` (int_trail_lines__at_chains), and a network
-- line with no GlobalID, OBJECTID or Socrata id is
-- `generated-<layer_position>` (int_trail_lines__network_judged). Both are a place in an ordering, so
-- when a chain is added or a feature moves in its layer, every later id
-- carries different content. The history then reads that as edits to
-- those ids, not as one insertion: their `_changed_at` moves and their
-- `_first_seen_at` does not (Reasoned from the two derivations; not
-- measured on real data).
{{ config(unique_key='trail_line_id') }}
{{ row_history_snapshot('int_trail_lines__final') }}
{% endsnapshot %}
