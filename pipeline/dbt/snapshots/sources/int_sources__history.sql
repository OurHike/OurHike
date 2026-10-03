{% snapshot int_sources__history %}
-- The sources mart's row history (macros/row_history.sql).
{{ config(unique_key='source_key') }}
{{ row_history_snapshot('int_sources__final') }}
{% endsnapshot %}
