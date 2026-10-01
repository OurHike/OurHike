"""Volunteer work projects: reference/work_projects.json, reviewed in git, one row per project. Hourly, as a closure is.

0 rows on 2026-10-01: the file is the stopgap features/VOLUNTEERING.md names
until club admin tooling replaces it (lib/work_projects.py). A reviewed file
is its own proof, so an empty one loads as an empty table rather than being
refused, and a cancelled project clears with the next load (ELT.md, CL18).
OurHike's Postgres rows sit beside it, in closures.py, reports.py and
field_notes.py.
"""

from extract._kinds import reviewed_file

TYPE = "closures"
CLAIMS = ("reference/work_projects.json",)
RESOURCES = [reviewed_file("reference/work_projects.json", rows_key="rows")]
