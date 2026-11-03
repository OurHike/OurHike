{% snapshot int_challenges__history %}
-- The challenges mart's row history (macros/row_history.sql).
--
-- `list_position`, the row's place in today's path order, is left out of the
-- hash: a row added or removed above another moves that place and nothing
-- else about it. row_history_refresh() keeps the current version's place
-- current.
{{ config(unique_key='challenge_id') }}
{{ row_history_snapshot('int_challenges__final', skip=['list_position']) }}
{% endsnapshot %}
