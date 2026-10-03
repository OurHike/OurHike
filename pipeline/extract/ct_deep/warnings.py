"""Connecticut DEEP: warnings, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

The hunting areas are machine-readable. Fire danger exists but cannot be read by a fetcher today. Do
not route around the CAPTCHA: asking DEEP Forestry for a feed is the path. Skeptic, 2026-10-01: the
CAPTCHA is still there on re-test. A search of the DEEP AGOL org for "fire danger" returns 0 …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Read for this type (decision 53 phase B, 2026-10-03): the parks emergency-message page is wired in
closures.py (`ct_deep_parks_emergency_message`), and ctparks.com's per-park alert blocks are not,
for the reason closures.py gives. The forest-fire danger report
(https://www.depdata.ct.gov/forestry/forestfire/firerpt.cshtml) is refused by robots.txt
(`User-agent: *` / `Disallow: /forestry/forestfire/`, read by the decision 53 inventory, batch 2)
before its CAPTCHA is reached, so it is never fetched; the route forward is asking DEEP Forestry for
a feed or for permission.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services/Areas_Closed_to_Hunting/FeatureServer/0,
384 season-flag polygons saying which seasons apply where, not when;
https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services/DEEP_Trails_Set/FeatureServer/3,
TRAILSTAT 'Needs Repair' on 3 of about 13,883 trails, an inventory flag rather than a closure (a
trail_lines layer).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        '`Areas_Closed_to_Hunting/0`: 384 polygons, edited 2026-08-03 (empty `licenseInfo`). `Connecticut_Open_for_Hunting_New_Schema/0`: 178, edited 2026-08-03, with per-species and per-implement season flags. The Forest Fire Danger Report page `https://portal.ct.gov/deep/forestry/forest-fire/forest-fire-danger-report` embeds `https://www.depdata.ct.gov/forestry/forestfire/firerpt.cshtml`, which answered a CAPTCHA ("What code is in the image?").',
        "(the decision 53 inventory, batch 2, 2026-10-03) https://www.depdata.ct.gov/robots.txt, group `User-agent: *`: `Disallow: /forestry/forestfire/`, so the fire-danger report was not requested.",
    ),
    where=(
        "https://portal.ct.gov/deep/forestry/forest-fire/forest-fire-danger-report",
        "https://www.depdata.ct.gov/forestry/forestfire/firerpt.cshtml",
        "https://services1.arcgis.com/FjPcSmEFuDYlIdKC/arcgis/rest/services",
    ),
    terms="robots.txt (https://www.depdata.ct.gov/robots.txt), group 'User-agent: *': 'Disallow: /forestry/forestfire/'",
    reason="refused: robots.txt disallows the fire-danger report for every agent (quoted in `terms`); DEEP's hunting layers are season flags, not notices (closures.py's docstring)",
)
