{% snapshot int_points_of_interest__history %}
-- The points of interest mart's row history (macros/row_history.sql).
{{ config(unique_key='poi_id') }}
{{ row_history_snapshot('int_points_of_interest__final') }}
{% endsnapshot %}
