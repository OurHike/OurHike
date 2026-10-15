{% snapshot int_elevation__history %}
-- The elevation mart's row history (macros/row_history.sql).
--
-- KEYED BY POSITION. [line_id, seq] is a sample's place along its line, so
-- a line that gains a mile at its start moves every sample after it. The
-- history reads every one of them as an edit, which is a version per
-- sample in that build (Reasoned from the key; not measured on real data).
--
-- line_sample_key (decision 197) is left out of the hash: it is
-- generate_surrogate_key over this snapshot's own unique_key, so two
-- versions of one key cannot differ in it. Hashed, it would have opened a
-- second version of every sample in the first build that carried it
-- (row_hash.sql, "a column added"), and the history keeps every version.
-- Left out, the snapshot's post-hook copies it into each current version
-- (row_history_refresh()), beside _loaded_at.
{{ config(unique_key=['line_id', 'seq']) }}
{{ row_history_snapshot('int_elevation__final', skip=['line_sample_key']) }}
{% endsnapshot %}
