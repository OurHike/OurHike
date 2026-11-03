{% snapshot int_places__history %}
-- The places mart's row history (macros/row_history.sql).
--
-- `place_order`, the row's place in places.json, is left out of the hash: a
-- row added or removed above another moves that place and nothing else about
-- it. row_history_refresh() keeps the current version's place current.
{{ config(unique_key='place_id') }}
{{ row_history_snapshot('int_places__final', skip=['place_order']) }}
{% endsnapshot %}
