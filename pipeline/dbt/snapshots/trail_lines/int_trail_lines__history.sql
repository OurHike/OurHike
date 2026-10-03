{% snapshot int_trail_lines__history %}
-- The trail lines mart's row history (macros/row_history.sql).
{{ config(unique_key='trail_line_id') }}
{{ row_history_snapshot('int_trail_lines__final') }}
{% endsnapshot %}
