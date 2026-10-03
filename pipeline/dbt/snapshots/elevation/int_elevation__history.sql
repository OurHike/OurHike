{% snapshot int_elevation__history %}
-- The elevation mart's row history (macros/row_history.sql).
{{ config(unique_key=['line_id', 'seq']) }}
{{ row_history_snapshot('int_elevation__final') }}
{% endsnapshot %}
