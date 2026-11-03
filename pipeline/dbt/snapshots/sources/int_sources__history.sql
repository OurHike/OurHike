{% snapshot int_sources__history %}
-- The sources mart's row history (macros/row_history.sql).
--
-- `list_position`, the row's place in sources.json, is left out of the hash:
-- a row added or removed above another moves that place and nothing else
-- about it. row_history_refresh() keeps the current version's place current.
{{ config(unique_key='source_key') }}
{{ row_history_snapshot('int_sources__final', skip=['list_position']) }}
{% endsnapshot %}
