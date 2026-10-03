"""The Mountaineers: trail lines, could not be told (coverage audit 2026-10-01, batch p09_persist).

Stays UNKNOWN: the club's own site is the one place it would publish, and that site cannot be read.
KLF layer: licenseInfo empty (none_stated). Its `accessInformation` exposes two individuals' names,
phone numbers and emails, which are not copied here. The guidebook GPX are probably sold with the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Tried: (1) No ArcGIS host belonging to the club turned up. (2) AGOL `"The Mountaineers"` gave 7,598 '
        'fuzzy hits, none owned by the club; `owner:mountaineers` 0 (audit). Hub "Mountaineers Washington" gave'
        " 1,319 hits, none the club's. The nearest find is the Keta Legacy Foundation org (`fUZ4ZUl57GG2z81p`, "
        "117 items), which works on the Rhododendron Preserve near Bremerton. That the Preserve is a "
        "Mountaineers property is Reasoned and unchecked. Its "
        "`https://services9.arcgis.com/fUZ4ZUl57GG2z81p/arcgis/rest/services/2021_Trails_and_Roads/FeatureServer/1`"
        ' ("tracks_20210916") holds 7,972 polyline …',
    ),
    where=(
        "https://services9.arcgis.com/fUZ4ZUl57GG2z81p/arcgis/rest/services/2021_Trails_and_Roads/FeatureServer/1",
        "https://mountaineers.org/",
    ),
    reason="the coverage audit could not tell on 2026-10-01; checked says what stopped it",
)
