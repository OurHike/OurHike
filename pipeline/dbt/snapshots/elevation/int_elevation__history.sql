{% snapshot int_elevation__history %}
-- The elevation mart's row history (macros/row_history.sql).
--
-- KEYED BY POSITION. [line_id, seq] is a sample's place along its line, so
-- a line that gains a mile at its start moves every sample after it. The
-- history reads every one of them as an edit, which is a version per
-- sample in that build (Reasoned from the key; not measured on real data).
{{ config(unique_key=['line_id', 'seq']) }}
{{ row_history_snapshot('int_elevation__final') }}
{% endsnapshot %}
