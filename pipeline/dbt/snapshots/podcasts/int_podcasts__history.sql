{% snapshot int_podcasts__history %}
-- The podcasts mart's row history (macros/row_history.sql).
{{ config(unique_key='spotify_id') }}
{{ row_history_snapshot('int_podcasts__final') }}
{% endsnapshot %}
