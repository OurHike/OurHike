{#- When the extract last read a source's raw table, or confirmed it unchanged:
    the `loaded_at_query` of every source's freshness since decision 203 (the
    maintainer, 2026-10-15: freshness is OurHike's own last successful read,
    in every lane; make_dbt_staging.py's LOADED_AT_QUERY), and of every notice
    source's before it (the maintainer's poll of 2026-10-07: "Red
    after 24h. But this should be Red in the data source freshness feature of
    dbt. Not blocking a datasource pipeline"). The Python steps' own tables are
    the one exception: no run log row names them, so they keep `_loaded_at`.

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

    A table the log never mentions has not been asked yet: its source was
    registered after the extract that reads it last ran. It counts from the
    newest row the log holds for any table, which in the hourly warehouse is
    this run's own read, so it passes until the notices leg first asks about
    it, and in the monthly warehouse the monthly extract's newest. So does a
    table no extract reads at all: measured 2026-10-15 on the fixture
    warehouse, 15 of the 802 sources `dbt source freshness` measured had no
    row of their own (the run log itself, the two row-history tables, and 12
    tables the fixtures do not land), and all 15 passed on the log's newest. Before 2026-10-11 it read null, which dbt 2.0.6 reads as 1970-01-01:
    on publish-conditions.yml run 634 RATC's three notice sources, new in that
    build's code, turned the run red before the notices leg had once run the
    code that reads them, and each notice source added later would have done
    the same until the next notices run, up to 4 hours by its cron (Reasoned).
    What still alarms (Reasoned): tests/test_notice_source_freshness.py holds
    that every table tagged for the notices run log is one a notices leg
    reads, so a table missing from that log is one the leg has not run yet,
    and publish-conditions.yml fails the run when the notices copy it read is
    over 8 hours old. A log with no row at all still reads null, and so as
    stale (dbt 2.0.6, measured 2026-10-07 in a scratch project).

    The hourly warehouse holds the conditions leg's run log and the notices
    copy's beside it (extract/_warehouse.py's add_served()); the monthly and
    fixture warehouses hold their lane's. `checked_at` may be a naive UTC
    TIMESTAMP there rather than a TIMESTAMPTZ: dbt 2.0.6 read a naive one as
    UTC, under TZ=UTC and TZ=America/Los_Angeles alike (measured 2026-10-07 in
    the same scratch project), so it is not cast. -#}
{% macro last_read_or_confirmed_at(relation) -%}
    select
        coalesce(
            max(checked_at) filter (
                where table_name = '{{ relation.identifier }}'
                and outcome in ('loaded', 'skipped')
            ),
            min(checked_at) filter (
                where table_name = '{{ relation.identifier }}'
            ),
            max(checked_at)
        )
    from {{ source('extract', '_extract_runs') }}
{%- endmacro %}
