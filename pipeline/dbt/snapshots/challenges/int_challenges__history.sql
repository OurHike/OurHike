{% snapshot int_challenges__history %}
-- The challenges mart's row history (macros/row_history.sql).
{{ config(unique_key='challenge_id') }}
{{ row_history_snapshot('int_challenges__final') }}
{% endsnapshot %}
