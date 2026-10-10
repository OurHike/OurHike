"""Friends of the Mountains-to-Sea Trail: closures, from FMST's Hurricane Helene recovery map, hourly
(decision 53, phase B).

`fmst_helene_status` reads the Google My Maps map's KML export, one row per trail line with the
steward's own geometry: 12 lines on 2026-10-03, two of them CLOSED ("West of N Fork Catawba
crossing to east of N Fork Catawba crossing", 0.1 mi, and "Blue Ridge Parkway Boundary to NC 80",
2.6 mi, closed with a detour) and one a temporary detour (South Toe River, 7.7 mi). Each line's
status is in its description's "Trail Status" line and in its colour, both landed as served; dbt
reads which is closed, and only the steward's own "CLOSED" sets `obstructs_trail`.

What is not read: mountainstoseatrail.org itself, whose trail-updates and detour pages sit behind a
SiteGround captcha that answers even its robots.txt (the decision 53 inventory, 2026-10-03),
recorded and not worked round. The coverage audit (2026-10-01) found the detour pages by search:
`/possum-track-detour/`, `/south-toe-detour/`, `/i-540-detour/` (I-540 construction, "through
February 2028"), `/steels-creek-detour/`, `/harper-creek-detour/`, `/eno-river-state-park-detour/`,
and `/the-trail/trail-updates/`.
"""

from extract._json_apis import my_maps_placemarks

CLAIMS = ("fmst_helene_status",)
RESOURCES = [my_maps_placemarks("fmst_helene_status")]
