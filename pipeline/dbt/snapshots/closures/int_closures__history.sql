{% snapshot int_closures__history %}
-- The closures mart's row history (macros/row_history.sql).
--
-- TWO KEYS THAT ARE NOT AN ID (int_closures__unioned):
-- - an OPRHP closure is keyed by its name and geometry, so an edit to either
--   reads as one closure removed and another first seen;
-- - an ATC update without an atc_id is keyed by its row in the file, so a
--   row inserted above it gives its id to different content.
-- Reasoned from the key derivations; not measured on real data.
{{ config(unique_key='closure_id') }}
{{ row_history_snapshot('int_closures__final') }}
{% endsnapshot %}
