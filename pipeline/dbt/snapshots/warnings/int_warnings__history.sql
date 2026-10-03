{% snapshot int_warnings__history %}
-- The warnings mart's row history (macros/row_history.sql).
--
-- Its key is int_closures__unioned's notice_id, as the closures mart's is,
-- with the same two kinds that are not an id
-- (snapshots/closures/int_closures__history.sql says which).
{{ config(unique_key='warning_id') }}
{{ row_history_snapshot('int_warnings__final') }}
{% endsnapshot %}
