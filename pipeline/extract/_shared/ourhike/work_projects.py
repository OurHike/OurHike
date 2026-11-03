"""Volunteer work projects: reference/work_projects.json, reviewed in git, landed whole as one row. Hourly, as a closure is.

0 rows on 2026-10-01: the file is the stopgap features/VOLUNTEERING.md names
until club admin tooling replaces it (lib/work_projects.py). Landed whole
(`verbatim`, no `rows_key`), as reference/atc_updates.json is, for three
reasons: a table of no rows would have no columns for dbt to read; the
review (`reviewed_at`) and the retired `ua_sample_rows` key are facts about
the file, which lib/work_projects.py's is_reviewed() and file_problems()
read whatever `rows` holds; and each row stays as its reviewer wrote it, so
int_closures__work_projects_checked sees the mistakes file_problems()
refuses (CL17). The whole file is replaced whenever its bytes change, so a
cancelled project clears with the next load (ELT.md, CL18). OurHike's
Postgres rows sit beside it, in closures.py, reports.py and field_notes.py.
"""

from extract._kinds import reviewed_file

TYPE = "closures"
CLAIMS = ("reference/work_projects.json",)
RESOURCES = [reviewed_file("reference/work_projects.json", rows_key=None, verbatim=True)]
