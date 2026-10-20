{% snapshot int_points_of_interest__history %}
-- The points of interest mart's row history (macros/row_history.sql).
--
-- `record_order`, the row's place in its file, is left out of the hash: a row
-- added or removed above another moves that place and nothing else about it.
-- row_history_refresh() keeps the current version's place current.
{{ config(unique_key='poi_id') }}
{{ row_history_snapshot('int_points_of_interest__final', skip=['record_order']) }}
{% endsnapshot %}
