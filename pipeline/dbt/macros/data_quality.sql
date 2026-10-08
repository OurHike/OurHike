{#-
    data_quality.json, one lane's file for the public page at
    ourhike.org/data/quality/ (decision 102; pipeline/ELT.md, "Data quality
    (decision 102)"): every check this build ran, from the tables Elementary
    keeps them in, as counts and names. pub_data_quality writes the monthly
    lane's file and pub_conditions_data_quality the hourly lane's; each is
    `select` of this macro with its lane, and build_marts.py builds them in a
    pass of their own after Elementary's checks.

    COUNTS ONLY. Nothing here reads a row of any table a check tested, a
    sample, a coordinate or a check's own message. From Elementary's tables
    it reads names (table, column, test, metric), statuses, counts
    (`failures`, the rows a dbt test returned), timestamps, and the numbers an
    anomaly check measured and expected. It never reads
    test_results_description, `other` (an anomaly's anomalous_value, which
    for a freshness check is a row's own timestamp), result_rows, an anomaly
    row's anomaly_description or dimension_value, or a test's params beyond
    `days_back`. A measured number is carried only for the count_metrics
    below: a column's min or max is one row's own value, and an average or a
    length is a property of row values, so those checks carry their status
    and names, with every number null.

    PUBLISHED SOURCES ONLY (decision 10's rule for /data/). A check counts,
    and its table is named, only when nothing it tests holds a row of a
    source that may not publish:
    - a check that reads only marts, pub_ writers and seeds always counts:
      every mart but `sources` keeps only rows whose source may publish,
      `sources` is the registry (pipeline/sources.json, public in the
      repository), a writer's file is public, and a seed is committed;
    - a check that reads anything else (a raw table, a base or staging model,
      an intermediate, a snapshot, a step's derived table), a check on a
      writer that also reads an intermediate among them, counts only when no
      held source is upstream of anything it reads, by the project's own
      graph as Elementary's artifact tables hold it, a mart or a writer
      between them clearing it. In a fixture build, the expression_is_true
      checks on pub_trail_graph_profile and pub_trail_graph_elevation, which
      count int_trail_network__edges' rows, were held so (measured
      2026-10-08). A source publishes when int_sources__publication marks
      its key may_publish. Its key is its notice_readers row's source_key; else
      the key extract/_contract.py's raw_table() writes as the `<key>` of the
      extract's `raw_<folder>__<key>` name (`reference/challenges/atc` as
      `challenges_atc`); else `<folder>_<key>`, as
      unregistered_publishing_sources spells nws_alerts and opentrail_at. A
      source with no key the rules know (a step's derived table, the run log,
      a club's taxonomy terms, a reviewed file the registry has no row for) is
      held: anything the rules do not make true is false, as
      int_sources__publication reads a missing licence.
    - OurHike's own two source groups, `ourhike` and `registry`, are cleared.
      Every row in them is reviewed into this public repository
      (pipeline/sources.json, reference/*.json) or is one of the conditions
      database's public rows (_ourhike_conditions__sources.yml: verified
      closures, public reports, visible field notes, corroborated disputes).
      Held, they would hold nearly every intermediate, since every one that
      reads int_sources__publication reads the registry.
    - a check missing from Elementary's dbt_tests (its lineage unknown) is
      held.
    This reaches further than the contract the page was drawn to, which named
    raw and staging tables alone: an intermediate that unions a held source
    holds its rows too, and its row counts and failing-row counts would
    describe them.

    WHICH CHECKS ARE THIS BUILD'S. Elementary's tables hold the lane's history
    (restored before the build, decision 102 step 3), so a result is this
    build's when it was detected at or after OURHIKE_BUILD_STARTED_AT, which
    build_marts.py sets for every dbt command ('YYYY-MM-DD HH:MM:SS', UTC).
    Unset (a build by hand) every result counts as this build's, which is
    right only for a warehouse with no history. Of a test's runs in this
    build, the last one counts, so a test that failed and passed on a retry
    reads as passed. A skipped test ran nothing and is not counted.

    WHAT IT COSTS. Measured 2026-10-08 in a busy sandbox: the compiled SQL
    took 1.9 to 2.7 s over 835,810 results, about the 831,600 that 504
    hourly builds of 1,650 results each would leave in a 21-day history,
    with ten series of 166 points; the fixture build's pass, both writers in
    one dbt command, took 35.6 s, of which the two models ran side by side
    for 6.7 s and the hooks for 1.3 s: the rest is dbt starting and parsing.

    ONE CHECK is one dbt test; one table's freshness or volume; one schema
    test (a table's schema, whatever number of columns changed); and one
    column measure of an anomaly test (each column and metric of a
    column_anomalies test, as the page's "column measures" count them).

    THE FILE (format ourhike-data-quality/1; the contract the page is built
    against is decision 102's, and departures from it are named here):
    - `lane`: `monthly` or `hourly`; `built_at`: when this pass started, the
      last dbt command of the build, UTC to the second.
    - `totals` and `kinds`: checks, passed, warned, failed, errored; kinds
      always all five, in the page's order: freshness, volume, schema,
      dbt_tests, anomalies. A kind is the test's own name first, then
      Elementary's type and metric: freshness_anomalies and
      event_freshness_anomalies, and a table_anomalies metric of freshness or
      event_freshness, are `freshness`; volume_anomalies and a row_count
      metric `volume`; schema_changes, schema_changes_from_baseline,
      exposure_schema_validity and json_schema `schema` (Elementary types
      exposure_schema_validity a dbt test; ELT.md's table of checks puts it
      under Schema); every other anomaly test `anomalies`; every other test
      `dbt_tests`.
    - `learning`: `builds`, the check runs (one per build: build_marts.py runs
      Elementary's checks once) the lane's history holds anomaly results
      from, this build's included; `needed`, Elementary's
      min_training_set_size (0.26.0's get_config_var.sql: 7, unless the
      project's vars set it). @unvalidated whether a check's own
      min_training_set_size, if one is ever set per test, should win: 0.26.0
      does not store it in a result's test_params (Measured 2026-10-08, a
      scratch project), so it cannot be read back here.
    - `needs_a_look`: every counted check whose status is not pass, worst
      first (error, fail, warn), then by kind, table, column and test, each
      {kind, table, column, status, value, expected_min, expected_max, since,
      metric, test}.
      `table` is the table Elementary's result names (the test's one parent);
      else, for a test that reads several and names none, the first by name
      of the relations it reads; else the test's own name. Never null: the
      page reads a file with a nameless entry as unreadable
      (site/src/lib/dataQuality.mjs, parse()), and 36 of the 5,025 results
      of a fixture build named no table, every one a singular test (measured
      2026-10-08; all 36 passed, so none reached needs_a_look that time).
      `metric` is Elementary's own name for what an anomaly check measured
      (row_count, freshness, event_freshness, null_count, null_percent, min,
      max, dimension, ...), null where its result names none, and null for a
      dbt test and for a schema change (the contract as the lead amended it,
      2026-10-08). Every number is in
      Elementary's own units, which this file never converts: freshness and
      event_freshness in seconds (0.26.0's table_monitoring_query.sql takes
      each as timediff("second", ...)), each *_percent from 0 to 100
      (percent_query.sql: value / total * 100.0, to 3 places), and counts as
      counts. `test`, an addition to the contract, is the test's short name
      (not_null, volume_anomalies, schema_changes, a singular test's own
      name), without which a dbt test's or a schema change's entry could not
      say what ran.
      `value` is a dbt test's failing rows; an anomaly's measured value at
      its anomalous bucket, with Elementary's expected band there (whole
      numbers for the whole_metrics below, the band to 3 places); a dimension
      anomaly's number of dimension values out of band (the values themselves
      are row values, never written); and null for an error and for a schema
      change. A schema test lists one entry per changed column.
      `since` is when the check's current run of non-passing results began,
      by the lane's history: this file's own built_at when it began in this
      build, which is how the page says "since this build"; else when that
      run's first result was detected.
    - `series`: what the page's line chart can draw, one entry per table and
      metric, each {table, metric, points}, its points the metric's history
      within the check's training window (its `days_back`, Elementary's 14
      days by default) from data_monitoring_metrics, each {at, value,
      expected_min, expected_max}, the band where a check scored that point
      and null where none did. Which tables is one parameter, the dbt var
      `data_quality_series`, so a wider scope is a one-line change (its
      default below, or a `vars:` line in dbt_project.yml):
        needs_a_look          the metric behind each volume and freshness
                              entry of needs_a_look (the default, the
                              contract's);
        mart_row_counts       the row count of every table under
                              models/marts/ whose volume check counted;
        published_row_counts  the row count of every table whose volume
                              check counted, raw, staging and intermediate
                              included: every one the rule above publishes.
      The two wider scopes draw only what Elementary measured, so a table
      with no volume check has no series.
    - `by_mart`: the counted checks on each mart's own models, its
      intermediate folder, its snapshot and its folder of singular tests
      (models/marts/<mart>/, models/intermediate/<mart>/, snapshots/<mart>/,
      tests/<mart>/), as totals, by mart name. Staging and raw tables belong to
      no one mart.

    Measured 2026-10-08 on dbt 2.0.6, Elementary 0.26.0 and DuckDB, in a
    scratch project of one source and one model over nine builds, the shapes
    read here: a schema change's row names its table in capitals (RAW,
    THINGS), so every name is lowercased; an anomaly test's scored buckets are
    in test_result_rows, one JSON row each (bucket_end, metric_value,
    min_metric_value, max_metric_value, is_anomalous), keyed by its
    elementary_test_results id, with test_sample_row_count 0; a check's status
    is pass, warn, fail or error; and data_monitoring_metrics names a table
    DATABASE.SCHEMA.TABLE in capitals.
-#}
{% macro data_quality_document(lane) -%}
    {%- if lane not in ('monthly', 'hourly') -%}
        {{ exceptions.raise_compiler_error("data_quality_document's lane is 'monthly' or 'hourly', not '" ~ lane ~ "'") }}
    {%- endif -%}
    {#- Each guard reads false under SQLFluff's jinja templater, which lints
        the stand-in; dbt always renders the first branch. -#}
    {%- set started = env_var('OURHIKE_BUILD_STARTED_AT', '') if env_var is defined else '' -%}
    {%- set needed = elementary.get_config_var('min_training_set_size') if elementary is defined else 7 -%}
    {%- if run_started_at is defined -%}
        {%- set built_at = run_started_at.strftime('%Y-%m-%dT%H:%M:%SZ') -%}
    {%- else -%}
        {%- set built_at = '1970-01-01T00:00:00Z' -%}
    {%- endif -%}
    {#- OurHike's own dbt source groups (the header, "PUBLISHED SOURCES
        ONLY"). -#}
    {%- set own_sources = ['ourhike', 'registry'] -%}
    {#- The metrics whose value is a count, a rate or an age, never a row's
        own value (the header, "COUNTS ONLY"). -#}
    {%- set count_metrics = [
        'row_count', 'freshness', 'event_freshness',
        'null_count', 'null_percent', 'not_null_percent',
        'zero_count', 'zero_percent', 'not_zero_percent',
        'missing_count', 'missing_percent', 'not_missing_percent',
        'count_true', 'count_false'
    ] -%}
    {#- Of those, the ones Elementary measures in whole numbers, rows or
        seconds (its freshness is a timediff in seconds), which it stores as a
        4-byte FLOAT: written as integers, which round() gives back exactly up
        to 2^24, 16,777,216, past which the FLOAT itself had already rounded. -#}
    {%- set whole_metrics = [
        'row_count', 'freshness', 'event_freshness',
        'null_count', 'zero_count', 'missing_count', 'count_true', 'count_false'
    ] -%}
    {#- Which tables `series` draws (the header, "series"): the one
        parameter. Its guard is `exceptions`, which SQLFluff's jinja
        templater does not define, because its var() gives back a stand-in
        ('item') rather than the default. -#}
    {%- set series_scopes = ['needs_a_look', 'mart_row_counts', 'published_row_counts'] -%}
    {%- set series_scope = var('data_quality_series', 'needs_a_look') if exceptions is defined else 'needs_a_look' -%}
    {%- if series_scope not in series_scopes -%}
        {{ exceptions.raise_compiler_error(
            "data_quality_series is one of " ~ series_scopes | join(", ") ~ ", not '" ~ series_scope ~ "'"
        ) }}
    {%- endif -%}
with recursive

-- Every result the lane's history holds, skipped runs left out, each with
-- its status as a rank (0 pass, 1 warn, 2 fail, 3 error or anything else)
-- and its metric: an anomaly's metric or a schema change, else null.
results as (
    select
        id as result_id,
        test_unique_id,
        invocation_id,
        coalesce(detected_at, created_at) as detected_at,
        created_at,
        upper(concat_ws('.', database_name, schema_name, table_name)) as full_table_name,
        lower(table_name) as table_name,
        lower(column_name) as column_name,
        test_type,
        test_short_name,
        failures,
        try_cast(json_extract_string(test_params, '$.days_back') as integer) as days_back,
        case lower(status)
            when 'pass' then 0
            when 'warn' then 1
            when 'fail' then 2
            else 3
        end as status_rank,
        case
            when
                test_type in ('anomaly_detection', 'schema_change')
                and test_sub_type not in ('generic', 'singular')
                then lower(test_sub_type)
        end as metric
    from {{ ref('elementary', 'elementary_test_results') }}
    where test_unique_id is not null and lower(status) != 'skipped'
),

this_build as (
    select * from results
    {%- if started %}
    where detected_at >= cast('{{ started | replace("'", "''") }}' as timestamp)
    {%- endif %}
),

-- A test's last run in this build: a retry's, when one ran.
last_runs as (
    select
        test_unique_id,
        arg_max(invocation_id, created_at) as invocation_id
    from this_build
    group by test_unique_id
),

classified as (
    select
        this_build.*,
        case
            when this_build.test_short_name in ('freshness_anomalies', 'event_freshness_anomalies') then 'freshness'
            when this_build.test_short_name = 'volume_anomalies' then 'volume'
            when
                this_build.test_short_name in (
                    'schema_changes', 'schema_changes_from_baseline', 'exposure_schema_validity', 'json_schema'
                )
                then 'schema'
            when
                this_build.test_type = 'anomaly_detection'
                and this_build.metric in ('freshness', 'event_freshness')
                then 'freshness'
            when this_build.test_type = 'anomaly_detection' and this_build.metric = 'row_count' then 'volume'
            when this_build.test_type = 'schema_change' then 'schema'
            when this_build.test_type = 'anomaly_detection' then 'anomalies'
            else 'dbt_tests'
        end as kind
    from this_build
    inner join last_runs
        on
            this_build.test_unique_id = last_runs.test_unique_id
            and this_build.invocation_id = last_runs.invocation_id
),

-- The project's graph, as Elementary's artifact tables hold it.
graph_nodes as (
    select
        unique_id,
        original_path,
        depends_on_nodes
    from {{ ref('elementary', 'dbt_models') }}
    union all
    select
        unique_id,
        original_path,
        depends_on_nodes
    from {{ ref('elementary', 'dbt_snapshots') }}
),

edges as (
    select
        unique_id as child,
        unnest(from_json(depends_on_nodes, '["VARCHAR"]')) as parent
    from graph_nodes
),

-- The nodes whose rows may all be published: marts and writers. A held
-- source's rows stop at them, so nothing below one is held by what is above.
cleared as (
    select unique_id from graph_nodes
    where original_path like 'models/marts/%' or original_path like 'models/publish/%'
),

readers as (
    select
        raw_table,
        source_key
    from {{ ref('notice_readers') }}
),

publication as (
    select
        source_key,
        may_publish
    from {{ ref('int_sources__publication') }}
),

raw_tables as (
    select
        unique_id,
        source_name,
        coalesce(identifier, name) as raw_table
    from {{ ref('elementary', 'dbt_sources') }}
),

-- Each node's table as Elementary's results name one (0.26.0's
-- get_table_name_from_node.sql): a source's identifier, else an alias, else
-- the node's name.
relation_names as (
    select
        unique_id,
        lower(raw_table) as relation_name
    from raw_tables
    union all
    select
        unique_id,
        lower(coalesce(alias, name)) as relation_name
    from {{ ref('elementary', 'dbt_models') }}
    union all
    select
        unique_id,
        lower(coalesce(alias, name)) as relation_name
    from {{ ref('elementary', 'dbt_snapshots') }}
    union all
    select
        unique_id,
        lower(coalesce(alias, name)) as relation_name
    from {{ ref('elementary', 'dbt_seeds') }}
),

-- Each key as extract/_contract.py's raw_table() writes it into a table's
-- name: `reference/` and `.json` dropped, `/` and `-` written `_`.
publication_tables as (
    select
        source_key,
        may_publish,
        replace(
            replace(regexp_replace(regexp_replace(source_key, '^reference/', ''), '[.]json$', ''), '/', '_'), '-', '_'
        ) as table_key
    from publication
),

-- Each source's verdict: its notice_readers row's key, else the key whose
-- table_key is the `<key>` of its `raw_<folder>__<key>` name, else
-- `<folder>_<key>`, the spelling of unregistered_publishing_sources'
-- nws_alerts and opentrail_at. A name two keys match gets both verdicts, and
-- either holds it.
source_verdicts as (
    select
        raw_tables.unique_id,
        raw_tables.source_name in ('{{ own_sources | join("', '") }}') as is_ourhikes,
        case
            when readers.raw_table is not null then by_reader.may_publish
            when by_key.table_key is not null then by_key.may_publish
            else by_folder_and_key.may_publish
        end as may_publish
    from raw_tables
    left join readers on raw_tables.raw_table = readers.raw_table
    left join publication as by_reader on readers.source_key = by_reader.source_key
    left join publication_tables as by_key
        on regexp_extract(raw_tables.raw_table, '^raw_[a-z0-9_]+?__(.+)$', 1) = by_key.table_key
    -- regexp_replace() gives back a name it does not match unchanged, and a
    -- step's derived.osm_water would then read as the registry's osm_water.
    left join publication as by_folder_and_key
        on
            regexp_matches(raw_tables.raw_table, '^raw_[a-z0-9_]+?__.+$')
            and regexp_replace(raw_tables.raw_table, '^raw_([a-z0-9_]+?)__(.+)$', '\1_\2') = by_folder_and_key.source_key
),

held_sources as (
    select distinct unique_id from source_verdicts
    where not is_ourhikes and not coalesce(may_publish, false)
),

-- Every node a held source reaches, down to the first mart or writer.
held_nodes (node) as (
    select unique_id from held_sources
    union
    select edges.child
    from edges
    inner join held_nodes on edges.parent = held_nodes.node
    left join cleared on edges.child = cleared.unique_id
    where cleared.unique_id is null
),

tests as (
    select
        unique_id as test_unique_id,
        original_path,
        depends_on_nodes,
        parent_model_unique_id
    from {{ ref('elementary', 'dbt_tests') }}
),

test_parents as (
    select
        test_unique_id,
        unnest(from_json(depends_on_nodes, '["VARCHAR"]')) as parent
    from tests
),

held_tests as (
    select distinct test_parents.test_unique_id
    from test_parents
    inner join held_nodes on test_parents.parent = held_nodes.node
),

-- A table for a test whose results name none, as a test that reads several
-- relations and was given no one parent has: the first by name of those it
-- reads (the header, "needs_a_look").
test_tables as (
    select
        test_parents.test_unique_id,
        min(relation_names.relation_name) as table_name
    from test_parents
    inner join relation_names on test_parents.parent = relation_names.unique_id
    group by test_parents.test_unique_id
),

marts as (
    select distinct regexp_extract(original_path, '^models/marts/([a-z0-9_]+)/', 1) as mart
    from graph_nodes
    where original_path like 'models/marts/%/%'
),

-- Each test's mart: its parent model's folder, else a singular test's own;
-- and whether its parent is a mart's own model.
test_marts as (
    select
        tests.test_unique_id,
        coalesce(model_marts.mart, singular_marts.mart) as mart,
        coalesce(graph_nodes.original_path like 'models/marts/%', false) as on_a_mart
    from tests
    left join graph_nodes on tests.parent_model_unique_id = graph_nodes.unique_id
    left join marts as model_marts
        on
            regexp_extract(
                graph_nodes.original_path, '^(?:models/marts|models/intermediate|snapshots)/([a-z0-9_]+)/', 1
            )
            = model_marts.mart
    left join marts as singular_marts
        on regexp_extract(tests.original_path, '^tests/([a-z0-9_]+)/', 1) = singular_marts.mart
),

-- This build's results of the checks that count.
counted as (
    select
        classified.*,
        test_marts.mart,
        test_marts.on_a_mart
    from classified
    inner join test_marts on classified.test_unique_id = test_marts.test_unique_id
    left join held_tests on classified.test_unique_id = held_tests.test_unique_id
    where held_tests.test_unique_id is null
),

checks as (
    select
        any_value(kind) as kind,
        any_value(mart) as mart,
        max(status_rank) as status_rank
    from counted
    group by
        test_unique_id,
        case when kind = 'schema' then '' else coalesce(column_name, '') end,
        case when kind = 'schema' then '' else coalesce(metric, '') end
),

kind_order as (
    select * from (
        values
        (1, 'freshness'),
        (2, 'volume'),
        (3, 'schema'),
        (4, 'dbt_tests'),
        (5, 'anomalies')
    ) as kind_order (kind_position, kind)
),

kinds as (
    select
        kind_order.kind_position,
        kind_order.kind,
        count(checks.kind) as checks,
        count(*) filter (where checks.status_rank = 0) as passed,
        count(*) filter (where checks.status_rank = 1) as warned,
        count(*) filter (where checks.status_rank = 2) as failed,
        count(*) filter (where checks.status_rank = 3) as errored
    from kind_order
    left join checks on kind_order.kind = checks.kind
    group by kind_order.kind_position, kind_order.kind
),

-- An anomaly result's scored buckets: numbers and the bucket's time only.
scores as (
    select
        elementary_test_results_id as result_id,
        created_at,
        lower(json_extract_string(result_row, '$.metric_name')) as metric,
        lower(json_extract_string(result_row, '$.column_name')) as column_name,
        json_extract_string(result_row, '$.dimension') is not null as by_dimension,
        try_cast(json_extract_string(result_row, '$.bucket_end') as timestamp) as bucket_end,
        try_cast(json_extract_string(result_row, '$.metric_value') as double) as metric_value,
        try_cast(json_extract_string(result_row, '$.min_metric_value') as double) as expected_min,
        try_cast(json_extract_string(result_row, '$.max_metric_value') as double) as expected_max,
        coalesce(try_cast(json_extract_string(result_row, '$.is_anomalous') as boolean), false) as is_anomalous
    from {{ ref('elementary', 'test_result_rows') }}
    where test_type = 'anomaly_detection'
),

anomalous as (
    select
        result_id,
        arg_max(metric_value, bucket_end) as metric_value,
        arg_max(expected_min, bucket_end) as expected_min,
        arg_max(expected_max, bucket_end) as expected_max
    from scores
    where is_anomalous and not by_dimension
    group by result_id
),

issues as (
    select
        counted.*,
        case
            when counted.status_rank = 3 then null
            when counted.metric = 'dimension' then to_json(counted.failures)
            when counted.metric in ('{{ whole_metrics | join("', '") }}')
                then to_json(cast(round(anomalous.metric_value) as bigint))
            when counted.metric in ('{{ count_metrics | join("', '") }}') then to_json(round(anomalous.metric_value, 3))
            when counted.kind = 'dbt_tests' then to_json(counted.failures)
            when counted.kind = 'schema' and counted.test_type = 'dbt_test' then to_json(counted.failures)
        end as value,
        case
            when counted.status_rank < 3 and counted.metric in ('{{ count_metrics | join("', '") }}')
                then round(anomalous.expected_min, 3)
        end as expected_min,
        case
            when counted.status_rank < 3 and counted.metric in ('{{ count_metrics | join("', '") }}')
                then round(anomalous.expected_max, 3)
        end as expected_max,
        -- The entry's table, never null (the header, "needs_a_look").
        coalesce(
            counted.table_name, test_tables.table_name, lower(counted.test_short_name), counted.test_unique_id
        ) as entry_table
    from counted
    left join anomalous on counted.result_id = anomalous.result_id
    left join test_tables on counted.test_unique_id = test_tables.test_unique_id
    where counted.status_rank > 0
),

-- Every run of each test the history holds, and each issue's status in it:
-- a run that reported nothing for the issue's column and metric passed it.
runs as (
    select
        test_unique_id,
        invocation_id,
        max(detected_at) as detected_at
    from results
    group by test_unique_id, invocation_id
),

issue_runs as (
    select
        issues.result_id,
        runs.detected_at,
        coalesce(max(earlier.status_rank), 0) as status_rank
    from issues
    inner join runs on issues.test_unique_id = runs.test_unique_id
    left join results as earlier
        on
            runs.test_unique_id = earlier.test_unique_id
            and runs.invocation_id = earlier.invocation_id
            and coalesce(issues.column_name, '') = coalesce(earlier.column_name, '')
            and coalesce(issues.metric, '') = coalesce(earlier.metric, '')
    group by issues.result_id, runs.invocation_id, runs.detected_at
),

last_passes as (
    select
        result_id,
        max(detected_at) filter (where status_rank = 0) as passed_at
    from issue_runs
    group by result_id
),

sinces as (
    select
        issue_runs.result_id,
        min(issue_runs.detected_at) as since
    from issue_runs
    inner join last_passes on issue_runs.result_id = last_passes.result_id
    where
        issue_runs.status_rank > 0
        and (last_passes.passed_at is null or issue_runs.detected_at > last_passes.passed_at)
    group by issue_runs.result_id
),

-- The tables and metrics `series` draws, as series_scope names them (the
-- header, "series"), one row each; the first of its checks by id stands for
-- the table where the band is read. Each table's history is deduplicated by
-- bucket below (Elementary rewrites its recent buckets) and kept within the
-- check's window.
charted as (
    select
        full_table_name,
        any_value(table_name) as table_name,
        metric,
        min(test_unique_id) as test_unique_id,
        max(coalesce(days_back, 14)) as days_back
    {%- if series_scope == 'needs_a_look' %}
    from issues
    where
        kind in ('freshness', 'volume')
        and metric in ('row_count', 'freshness', 'event_freshness')
    {%- else %}
    from counted
    where
        kind = 'volume'
        and metric = 'row_count'
        {%- if series_scope == 'mart_row_counts' %}
        and on_a_mart
        {%- endif %}
    {%- endif %}
        and table_name is not null
    group by full_table_name, metric
),

metric_points as (
    select
        charted.test_unique_id,
        metrics.bucket_end,
        arg_max(metrics.metric_value, metrics.updated_at) as metric_value
    from charted
    inner join {{ ref('elementary', 'data_monitoring_metrics') }} as metrics
        on
            upper(metrics.full_table_name) = charted.full_table_name
            and lower(metrics.metric_name) = charted.metric
            and metrics.column_name is null
            and metrics.dimension is null
    group by charted.test_unique_id, metrics.bucket_end
),

windows as (
    select
        charted.test_unique_id,
        max(metric_points.bucket_end) - to_days(any_value(charted.days_back)) as starts_after
    from charted
    inner join metric_points on charted.test_unique_id = metric_points.test_unique_id
    group by charted.test_unique_id
),

-- The band a run of the check gave each bucket it scored, its last run's.
bands as (
    select
        results.test_unique_id,
        scores.bucket_end,
        arg_max(scores.expected_min, scores.created_at) as expected_min,
        arg_max(scores.expected_max, scores.created_at) as expected_max
    from scores
    inner join results on scores.result_id = results.result_id
    inner join charted on results.test_unique_id = charted.test_unique_id and scores.metric = charted.metric
    where not scores.by_dimension and scores.column_name is null
    group by results.test_unique_id, scores.bucket_end
),

series as (
    select
        charted.table_name,
        charted.metric,
        list(
            {
                'at': strftime(metric_points.bucket_end, '%Y-%m-%dT%H:%M:%SZ'),
                'value': cast(round(metric_points.metric_value) as bigint),
                'expected_min': round(bands.expected_min, 3),
                'expected_max': round(bands.expected_max, 3)
            }
            order by metric_points.bucket_end
        ) as points
    from charted
    inner join metric_points on charted.test_unique_id = metric_points.test_unique_id
    inner join windows on charted.test_unique_id = windows.test_unique_id
    left join bands
        on
            charted.test_unique_id = bands.test_unique_id
            and metric_points.bucket_end = bands.bucket_end
    where metric_points.bucket_end > windows.starts_after
    group by charted.test_unique_id, charted.table_name, charted.metric
),

marts_tally as (
    select
        mart,
        count(*) as checks,
        count(*) filter (where status_rank = 0) as passed,
        count(*) filter (where status_rank = 1) as warned,
        count(*) filter (where status_rank = 2) as failed,
        count(*) filter (where status_rank = 3) as errored
    from checks
    where mart is not null
    group by mart
)

select
    'ourhike-data-quality/1' as format,
    '{{ lane }}' as lane,
    '{{ built_at }}' as built_at,
    (
        select
            to_json({
                'checks': count(*),
                'passed': count(*) filter (where status_rank = 0),
                'warned': count(*) filter (where status_rank = 1),
                'failed': count(*) filter (where status_rank = 2),
                'errored': count(*) filter (where status_rank = 3)
            })
        from checks
    ) as totals,
    (
        select
            to_json(list({
                'kind': kind,
                'checks': checks,
                'passed': passed,
                'warned': warned,
                'failed': failed,
                'errored': errored
            } order by kind_position))
        from kinds
    ) as kinds,
    (
        select
            to_json({
                'builds': count(distinct invocation_id),
                'needed': {{ needed | int }}
            })
        from results
        where test_type = 'anomaly_detection'
    ) as learning,
    (
        select
            coalesce(
                to_json(list({
                    'kind': issues.kind,
                    'table': issues.entry_table,
                    'column': issues.column_name,
                    'status': case issues.status_rank when 1 then 'warn' when 2 then 'fail' else 'error' end,
                    'value': issues.value,
                    'expected_min': issues.expected_min,
                    'expected_max': issues.expected_max,
                    -- This file's own stamp for a run that began in this build
                    -- (the header, "needs_a_look").
                    'since': case
                        when sinces.since is null then null
                        {%- if started %}
                        when sinces.since < cast('{{ started | replace("'", "''") }}' as timestamp)
                            then strftime(sinces.since, '%Y-%m-%dT%H:%M:%SZ')
                        {%- endif %}
                        else '{{ built_at }}'
                    end,
                    -- An anomaly check's metric alone; a schema change's kind
                    -- of change stays out (the header, "needs_a_look").
                    'metric': case when issues.test_type = 'anomaly_detection' then issues.metric end,
                    'test': issues.test_short_name
                } order by
                    issues.status_rank desc,
                    kind_order.kind_position,
                    issues.entry_table,
                    issues.column_name nulls last,
                    issues.test_short_name,
                    issues.metric nulls last,
                    issues.test_unique_id)),
                cast('[]' as json)
            )
        from issues
        inner join kind_order on issues.kind = kind_order.kind
        left join sinces on issues.result_id = sinces.result_id
    ) as needs_a_look,
    (
        select
            coalesce(
                to_json(list({
                    'table': table_name,
                    'metric': metric,
                    'points': points
                } order by table_name, metric)),
                cast('[]' as json)
            )
        from series
    ) as series,
    (
        select
            coalesce(
                to_json(list({
                    'mart': mart,
                    'checks': checks,
                    'passed': passed,
                    'warned': warned,
                    'failed': failed,
                    'errored': errored
                } order by mart)),
                cast('[]' as json)
            )
        from marts_tally
    ) as by_mart
{%- endmacro %}
