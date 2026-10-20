"""OurHike's reviewed blaze mapping: reference/blaze_mapping.json, landed whole as `raw_ourhike__blaze_mapping`.

Per-source tables of what a raw value IS as paint on a tree (#782,
features/NEARBY_TRAILS.md section 4), each row somebody's reviewed decision;
lib/blaze.py reads it for export_trails.py and export_nearby_trails.py today
(ledger row TL03). One row, the whole document as written (ReviewedFile's
`verbatim`), because the tables are keyed by source key with no list to be
rows of, and because a typed load would coerce exactly the values a review
decided: a colour written as a number would land as text with nobody
having written it so.
"""

from extract._kinds import reviewed_file

TYPE = "trail_lines"
CLAIMS = ("reference/blaze_mapping.json",)
RESOURCES = [reviewed_file("reference/blaze_mapping.json", rows_key=None, verbatim=True)]
