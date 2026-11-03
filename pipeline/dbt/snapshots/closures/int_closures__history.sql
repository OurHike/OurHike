{% snapshot int_closures__history %}
-- The closures mart's row history (macros/row_history.sql).
--
-- TWO KEYS THAT ARE NOT AN ID (int_closures__unioned):
-- - an OPRHP closure is keyed by its name and geometry, so an edit to either
--   reads as one closure removed and another first seen;
-- - an ATC update without an atc_id is keyed by its row in the file, so a
--   row inserted above it gives its id to different content.
-- Reasoned from the key derivations; not measured on real data.
--
-- `list_position`, the row's place in its source file, is left out of the
-- hash: a row added or removed above another moves that place and nothing
-- else about it. row_history_refresh() keeps the current version's place
-- current.
{{ config(unique_key='closure_id') }}
{{ row_history_snapshot('int_closures__final', skip=['list_position']) }}
{% endsnapshot %}
