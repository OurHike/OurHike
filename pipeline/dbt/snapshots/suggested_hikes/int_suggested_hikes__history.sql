{% snapshot int_suggested_hikes__history %}
-- The suggested hikes mart's row history (macros/row_history.sql).
{{ config(unique_key='hike_id') }}
{{ row_history_snapshot('int_suggested_hikes__final') }}
{% endsnapshot %}
