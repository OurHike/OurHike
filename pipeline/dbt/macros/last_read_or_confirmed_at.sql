{#- When the extract last read a source's raw table, or confirmed it unchanged:
    the `loaded_at_query` of every notice source's freshness (decision 100, the
    maintainer's poll of 2026-10-07: "Red after 24h. But this should be Red in
    the data source freshness feature of dbt. Not blocking a datasource
    pipeline").

    It reads the extract's run log, never the table's `_loaded_at`. A
    `_loaded_at` is stamped only when a resource runs, so a source whose change
    check answers FRESH keeps its last load's stamp (the dlt skill, "the rest
    of .dlt configuration"), and a quiet, healthy source would read as days
    old. The run log has a row per resource per run that checked it
    (extract/_run.py's write_run_log()): `loaded` when the run read it,
    `skipped` when its check found it unchanged, and `refused`, `incomplete`
    or `unavailable` when neither happened. So this is the newest `loaded` or
    `skipped` row's `checked_at`, the same two outcomes extract/_run.py's due()
    counts as a check, and a refused run never moves it.

    A table with no such row at all (refused on every run so far, or waiting
    its turn) counts from the first row the log holds for it, the first time
    the extract asked: a source registered this morning has not gone 24
    hours unread. The leg's kept log holds every row of a table that has never
    loaded (extract/_run.py's kept_log()), so that first row is the first ask.
    A table the log never mentions reads null, which dbt 2.0.6 reads as
    1970-01-01 and so as stale (measured 2026-10-07 in a scratch project).

    The hourly warehouse holds the conditions leg's run log and the notices
    copy's beside it (extract/_warehouse.py's add_served()); the monthly and
    fixture warehouses hold their lane's. `checked_at` may be a naive UTC
    TIMESTAMP there rather than a TIMESTAMPTZ: dbt 2.0.6 read a naive one as
    UTC, under TZ=UTC and TZ=America/Los_Angeles alike (measured 2026-10-07 in
    the same scratch project), so it is not cast. -#}
{% macro last_read_or_confirmed_at(relation) -%}
    select
        coalesce(
            max(checked_at) filter (where outcome in ('loaded', 'skipped')),
            min(checked_at)
        )
    from {{ source('extract', '_extract_runs') }}
    where table_name = '{{ relation.identifier }}'
{%- endmacro %}
