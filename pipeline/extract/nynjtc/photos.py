"""NYNJTC's hike photographs: the 119 in reference/nynjtc_hike_photos.json, reviewed in git, one row each.

They were recovered once from the Wayback Machine by
fetch_wayback_hike_photos.py, and ship on the maintainer's relay of NYNJTC's
permission (`nynjtc_hikes_licence`), not on an open licence; 113 of the 119
credit a named individual. This loads the reviewed file's rows, credits
included, and never the pictures: photos land as manifest rows, never pixels
(coverage audit 2026-10-01, batch b2_nynjtc).
"""

from extract._kinds import reviewed_file

CLAIMS = ("reference/nynjtc_hike_photos.json",)
RESOURCES = [reviewed_file("reference/nynjtc_hike_photos.json", rows_key="photos")]
