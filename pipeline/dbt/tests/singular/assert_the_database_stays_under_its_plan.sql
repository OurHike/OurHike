-- OurHike's own database stays under its hosting plan. Supabase's Free plan
-- turns the database read-only past 500 MB
-- (supabase.com/docs/guides/platform/database-size, read 2026-10-27), and a
-- read-only database refuses every write the app makes, hazard reports
-- included. The maintainer's poll of 2026-10-28 on #1902 — Count six usage
-- events with a sealed account id and GPS fix, keep them six months, close
-- each month into a table, and report them per club, "Hourly dbt check, with
-- megabytes", put the size on the public data-quality page with its history.
--
-- So this test's `failures` is no count of rows and no level: it is the
-- database's size in whole megabytes, on every run, passing or not (measured
-- 2026-10-28 on dbt 2.0.6 and Elementary 0.26.0: a passing run over the
-- fixture's 150 MB recorded `failures` 150 in elementary_test_results), and
-- its meta's `measures` names it for macros/data_quality.sql, which publishes
-- it and its history as `database_mb`. It warns from 400 MB and errors from
-- 475 MB, 80% and 95% of 500, the thresholds the same poll chose. The
-- warning is the backend's own line, app/core/analytics_quality.py's
-- database_near_quota at STORAGE_WARN_SHARE of `database_quota_mb`, and
-- backend/tests/test_database_size_agrees.py holds warn_if to it. In
-- production and UA an error turns the hourly run red after closures and
-- warnings have published (build_marts.py, "EVERY TEST HAS TWO
-- THRESHOLDS"); in dev and CI it fails the build. A paid plan moves all three
-- numbers (features/EVENTING.md §0, "Operating it").
--
-- A leg that has never landed the size leaves no row, which is a size of 0
-- here and passes. macros/data_quality.sql writes a 0 as no value and no
-- point, because no database is 0 MB, and the source's freshness on the same
-- page says the size went unread.
{{ config(
    fail_calc="coalesce(max(database_mb), 0)",
    warn_if='>399',
    error_if='>474',
    meta={'measures': 'database_mb'}
) }}

select database_mb
from {{ ref('base_ourhike__database_size') }}
