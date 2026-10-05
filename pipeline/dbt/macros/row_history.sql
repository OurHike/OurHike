{#-
    ROW HISTORY: when each mart row was first seen and when it last changed.

    Decision 57 (the maintainer, poll, 2026-10-03, amending decision 52):
    one snapshot per mart, built in the intermediate layer, holding every
    contracted column, so that a removed feature keeps its last content and
    a later decision can merge removed features back. Only marts carry
    `_first_seen_at` and `_changed_at`.

    THE SHAPE, one chain per mart:

        int_<mart>__final -> int_<mart>__history -> <mart>

    - int_<mart>__final (models/intermediate/<mart>/) is what the mart's SQL
      was: exactly the mart's contracted columns, the two dates aside.
    - int_<mart>__history (snapshots/<mart>/, schema `intermediate`) is a
      dbt snapshot of it: the whole row, plus `_row_hash` (macros/row_hash.sql
      over every column but `_loaded_at`), which the check strategy compares,
      and `_built_by`, the build that wrote the version, which it does not.
      dbt_project.yml's `snapshots:` block sets the rest. A column the hash
      leaves out is refreshed in the current version after every snapshot
      (row_history_refresh() below), so it is this build's, never the value
      it had when the version opened.
    - <mart> is row_history_mart(): the snapshot's current rows and their
      two dates. A removed row is in the snapshot with dbt_valid_to set and
      is NOT in the mart: row_history_removed() below is the hook for the
      later decision on how removed features merge back.

    dbt 2.0.6 behaviour this rests on, measured 2026-10-03 in a scratch
    project on DuckDB (pipeline/ELT.md, "Row dates (decision 52)", has the
    list): a SQL snapshot block with strategy check, check_cols
    [_row_hash], unique_key (one column, or a list) and hard_deletes
    invalidate kept an unchanged row's one version across builds, opened a
    new version for an edited row, and set dbt_valid_to on a row that
    disappeared; `dbt build` ran the model it reads, then the snapshot, then
    the models that read it.
-#}

{#- The body of every int_<mart>__history snapshot: the final model's whole
    row, its hash, and the build that wrote it. `skip` adds columns to leave
    out of the hash beyond row_hash_load_columns(), for a column that changes
    on every run while the row does not. It also gives the snapshot its
    post-hook, row_history_refresh() with the same `skip`, so the columns
    left out of the hash are named once.

    Example, snapshots/closures/int_closures__history.sql, inside its
    snapshot block after the block's one config:

        {{ config(unique_key='closure_id') }}
        {{ row_history_snapshot('int_closures__final') }}

    `_built_by` is OURHIKE_BUILT_BY, which build_marts.py fills with the git
    commit and the workflow run, so a reader can tell a change upstream from
    a change to this project's rules: a version written by a new commit on
    unchanged raw is a rule change. It is never hashed, so it never opens a
    version by itself. -#}
{% macro row_history_snapshot(model_name, skip=[]) -%}
    {%- set relation = ref(model_name) -%}
    {{ config(post_hook=[
        "{{ row_history_refresh('" ~ model_name ~ "', " ~ (skip | tojson) ~ ") }}"
    ]) }}
    select
        *,
        {{ row_hash(relation, row_hash_load_columns() + skip) }} as _row_hash,
        '{{ env_var('OURHIKE_BUILT_BY', 'unknown') }}' as _built_by
    from {{ relation }}
{%- endmacro %}

{#- The snapshot's post-hook: every column the hash leaves out
    (row_hash_load_columns() and `skip`), copied from the final model into
    the key's current version. dbt's check strategy writes a version's
    columns only when it opens it, so without this an unchanged row kept the
    `_loaded_at` of the load that first held its content: a podcasts reload
    moved int_podcasts__final's `_loaded_at` to 2026-12-01 and left the
    mart's at the earlier load (the review of PR #1805 — dlt → dbt
    re-platform as one go/no-go change, 2026-10-05), and a skipped position
    column would have kept its first place in its file. A hashed column
    needs no copy: an unchanged hash is unchanged content.

    A hook rather than the mart reading the final model beside the
    snapshot, because that second path from the final model to the mart is
    the one row_history_mart()'s header measured raising the evaluator's
    peak memory fourfold. The hook adds no edge: the snapshot reads the
    final model already. It reads only the key and the refreshed columns,
    and updates only current versions, so a closed version keeps the values
    it closed with. Measured 2026-10-05 on the fixture podcasts chain: one
    UPDATE of `_loaded_at` on 71 rows, 3.7 ms. -#}
{% macro row_history_refresh(model_name, skip=[]) -%}
    {%- set final = ref(model_name) -%}
    {%- set key = config.get('unique_key') -%}
    {%- set keys = [key] if key is string else key -%}
    {%- set wanted = (row_hash_load_columns() + skip) | map('lower') | list -%}
    {%- set refreshed = [] -%}
    {%- if execute -%}
        {%- for column in adapter.get_columns_in_relation(final) -%}
            {%- if column.name | lower in wanted -%}
                {%- do refreshed.append(adapter.quote(column.name)) -%}
            {%- endif -%}
        {%- endfor -%}
    {%- endif -%}
    {%- if refreshed %}
    update {{ this }}
    set {% for column in refreshed %}{{ column }} = final.{{ column }}{{ ', ' if not loop.last }}{% endfor %}
    from (
        select {{ (keys + refreshed) | join(', ') }} from {{ final }}
    ) as final
    where
        {{ this.identifier }}.dbt_valid_to is null
        {%- for column in keys %}
        and {{ this.identifier }}.{{ column }} = final.{{ column }}
        {%- endfor %}
    {%- else %}
    select 1
    {%- endif %}
{%- endmacro %}

{#- A mart: the snapshot's current rows, each with

    - `_first_seen_at`: the earliest dbt_valid_from of its key, so a feature
      that disappeared and came back keeps the date it was first seen;
    - `_changed_at`: the dbt_valid_from of its current version, the build
      that last saw its `_row_hash` change, or saw it come back;

    both TIMESTAMPTZ in UTC (dbt_valid_from is UTC wall time because
    duckdb__snapshot_get_time() below writes it so). `key` is the mart's key
    column, or a list of them.

    With OURHIKE_ROW_HISTORY=off the mart is the final model's rows with
    both dates null, and the snapshot is not read. build_marts.py sets it
    only on a conditions leg whose restore failed: that leg still publishes
    closures and warnings, with both dates null (unknown, never "new"), and
    saves nothing back. Only the branch's own ref is taken, so in that build
    the mart depends on the final model and not on the snapshot. Taking both
    in every build made a second path from the final model to the mart,
    which raised dbt_project_evaluator's peak memory from 1,451 MB on
    f4ca3e35 to 5,960 MB, one thread each (measured 2026-10-03), and
    needed an exception to its rejoin rule. (`env_var is defined` is false
    under SQLFluff's jinja templater, which lints the snapshot branch.)

    Example, models/marts/closures/closures.sql:

        {{ row_history_mart('int_closures__history', 'int_closures__final', 'closure_id') }} -#}
{% macro row_history_mart(history_name, final_name, key) -%}
    {%- set keys = [key] if key is string else key -%}
    {%- set history_off = env_var is defined and env_var('OURHIKE_ROW_HISTORY', 'on') == 'off' -%}
    {%- if not history_off %}
    {%- set history = ref(history_name) %}
    with history as (
        select * from {{ history }}
    ),

    first_seen as (
        select
            {{ keys | join(', ') }},
            min(dbt_valid_from) as first_valid_from
        from history
        group by {{ keys | join(', ') }}
    )

    select
        history.* exclude (_row_hash, _built_by, dbt_scd_id, dbt_updated_at, dbt_valid_from, dbt_valid_to),
        timezone('UTC', first_seen.first_valid_from) as _first_seen_at,
        timezone('UTC', history.dbt_valid_from) as _changed_at
    from history
    inner join first_seen
        on {% for column in keys %}history.{{ column }} = first_seen.{{ column }}{{ ' and ' if not loop.last }}{% endfor %}
    where history.dbt_valid_to is null
    {%- else %}
    select
        *,
        cast(null as timestamptz) as _first_seen_at,
        cast(null as timestamptz) as _changed_at
    from {{ ref(final_name) }}
    {%- endif %}
{%- endmacro %}

{#- THE HOOK FOR REMOVED FEATURES, read by no model today. The last version
    of every key the snapshot holds no current version of: a feature that
    left the mart, with the content it had when it left, `_removed_at`
    (its dbt_valid_to) and `_first_seen_at`. Decision 57 leaves how removed
    features merge back to a later decision. For A.T. POIs that decision
    meets the identity ledger, reference/poi_identity.json, which already
    issues tombstones (retired_poi.geojson): the two must end with one home.

    Example: {{ row_history_removed('int_closures__history', 'closure_id') }} -#}
{% macro row_history_removed(history_name, key) -%}
    {%- set keys = [key] if key is string else key -%}
    with history as (
        select * from {{ ref(history_name) }}
    ),

    keyed as (
        select
            *,
            row_number() over (
                partition by {{ keys | join(', ') }} order by dbt_valid_from desc
            ) as newest_first,
            min(dbt_valid_from) over (partition by {{ keys | join(', ') }}) as first_valid_from,
            count(*) filter (where dbt_valid_to is null) over (
                partition by {{ keys | join(', ') }}
            ) as current_versions
        from history
    )

    select
        * exclude (
            _row_hash, _built_by, dbt_scd_id, dbt_updated_at, dbt_valid_from, dbt_valid_to,
            newest_first, first_valid_from, current_versions
        ),
        timezone('UTC', first_valid_from) as _first_seen_at,
        timezone('UTC', dbt_valid_to) as _removed_at
    from keyed
    where newest_first = 1 and current_versions = 0
{%- endmacro %}

{#- A snapshot's history start: its earliest dbt_valid_from, as TIMESTAMPTZ,
    the build that first ran it. A mart row whose `_first_seen_at` equals it
    was already there when history began, so it was first published AT OR
    BEFORE that time, possibly long before. row_history.py writes the same
    value into the store's history.json at every save.

    Example: where _first_seen_at = {{ row_history_started_at('int_closures__history') }} -#}
{% macro row_history_started_at(history_name) -%}
    (select timezone('UTC', min(dbt_valid_from)) from {{ ref(history_name) }})
{%- endmacro %}

{#- dbt's snapshot clock, as UTC wall time whatever the machine's zone.
    dbt 2.0.6's own writes now()::timestamp, the wall time of the process's
    zone: with TZ=America/New_York a build at 14:29 UTC wrote 10:29, and
    `settings: {TimeZone: UTC}` in the profile did not change it; with this
    override the same run wrote 14:30 at 14:30 UTC (both measured
    2026-10-03 on dbt 2.0.6, a scratch project; the second run's SQL showed
    this macro's text where dbt's own had been). -#}
{% macro duckdb__snapshot_get_time() -%}
    timezone('UTC', now())
{%- endmacro %}

{#- `sql`, only in a build without the row history (OURHIKE_ROW_HISTORY=off,
    decision 58), and nothing otherwise: for a writer that must not publish
    what a missing history would make it publish. pub_conditions_notices
    keeps the phone's last file while a notice source is held, because with
    no history a held club's last good rows cannot be carried. A macro, so
    that SQLFluff's jinja templater, which defines no env_var, renders the
    model with the history on.

    Example: {{ when_row_history_is_off('where held.sources_held = 0') }} -#}
{% macro when_row_history_is_off(sql) -%}
    {%- if env_var is defined and env_var('OURHIKE_ROW_HISTORY', 'on') == 'off' -%}
        {{ sql }}
    {%- endif -%}
{%- endmacro %}
