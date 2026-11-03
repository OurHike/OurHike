{% snapshot int_suggested_hikes__history %}
-- The suggested hikes mart's row history (macros/row_history.sql).
--
-- `list_position`, the row's place in its file, is left out of the hash: a
-- row added or removed above another moves that place and nothing else about
-- it. row_history_refresh() keeps the current version's place current.
{{ config(unique_key='hike_id') }}
{{ row_history_snapshot('int_suggested_hikes__final', skip=['list_position']) }}
{% endsnapshot %}
