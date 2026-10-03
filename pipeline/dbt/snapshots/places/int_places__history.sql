{% snapshot int_places__history %}
-- The places mart's row history (macros/row_history.sql).
{{ config(unique_key='place_id') }}
{{ row_history_snapshot('int_places__final') }}
{% endsnapshot %}
