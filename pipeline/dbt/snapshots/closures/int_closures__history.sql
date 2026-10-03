{% snapshot int_closures__history %}
-- The closures mart's row history (macros/row_history.sql).
{{ config(unique_key='closure_id') }}
{{ row_history_snapshot('int_closures__final') }}
{% endsnapshot %}
