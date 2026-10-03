{% snapshot int_warnings__history %}
-- The warnings mart's row history (macros/row_history.sql).
{{ config(unique_key='warning_id') }}
{{ row_history_snapshot('int_warnings__final') }}
{% endsnapshot %}
