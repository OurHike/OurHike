"""OurHike's own database's size, as its hosting plan counts it: the pipeline's copy of the one query.

The public data-quality page shows the size, by the maintainer's poll of
2026-10-28 on #1902 — Count six usage events with a sealed account id and GPS
fix, keep them six months, close each month into a table, and report them per
club ("Hourly dbt check, with megabytes"): the whole database's size in
megabytes, its history, a warning from 400 MB and a failure from 475 MB, 80%
and 95% of the 500 MB past which Supabase's Free plan turns the database
read-only (supabase.com/docs/guides/platform/database-size, read 2026-10-27).
The usage tables' own share of it stays on the private usage report:
published, it would be usage volume, which poll 4 on the same issue kept
private.

The reading travels:
- extract/_kinds.py's DatabaseSize runs DATABASE_SIZE_SQL once an hour, in
  each conditions leg, as that leg's conditions reader, and lands the answer
  as `raw_ourhike__database_size`, one row;
- dbt's base_ourhike__database_size turns its bytes into whole megabytes
  (MEGABYTE), and tests/singular/assert_the_database_stays_under_its_plan.sql
  warns and fails on them;
- macros/data_quality.sql publishes that test's value and its history.

THE SAME QUERY AS THE BACKEND'S. backend/app/core/analytics_storage.py's
`_DATABASE_BYTES` is this text, run nightly as the rollup's role for the
private report's storage strip and its `database_near_quota` check, and
backend/tests/test_database_size_agrees.py holds the two texts equal, the
megabyte too, and the test's warning line to the backend's
STORAGE_WARN_SHARE of `database_quota_mb`. The two roles may still read
different sums: `pg_database_size` refuses a database the role may not
connect to, so each sums only the databases its own role may. @unvalidated
whether the conditions reader and the rollup's role may connect to the same
ones on a hosted project; running
`select datname from pg_database where has_database_privilege(oid, 'CONNECT')`
as each settles it. A database one of them cannot connect to makes that
reading low, the late direction for a warning.
"""

from __future__ import annotations

# Kept on one line, and written exactly as the backend's `_DATABASE_BYTES`, so
# backend/tests/test_database_size_agrees.py compares the two texts whole.
DATABASE_SIZE_SQL = "select coalesce(sum(pg_database_size(oid)), 0) from pg_database where has_database_privilege(oid, 'CONNECT')"

# A megabyte here is 1,048,576 bytes, as the backend's `_MB` is, so 400 MB on
# the public page is the backend's 80% of `database_quota_mb` to the byte.
MEGABYTE = 1024 * 1024
