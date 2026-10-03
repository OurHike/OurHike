{% snapshot int_trail_network__history %}
-- The trail network mart's row history (macros/row_history.sql).
{{ config(unique_key='edge_id') }}
{{ row_history_snapshot('int_trail_network__final') }}
{% endsnapshot %}
