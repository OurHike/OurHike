"""Lone Star Hiking Trail Club: closures, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

The 2024 GeoJSON is stale-risk. The club says "the USFS website is the official position."

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check):
https://lonestartrail.org/content.aspx?page_id=22&club_id=738078&module_id=678717 (html_page);
https://lonestartrail.org/content.aspx?page_id=3&club_id=738078 (html_page);
https://lonestartrail.org/popup.aspx?page_id=126&club_id=738078 (html_page).

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://www.arcgis.com/sharing/rest/content/items/26ead23c99224bdaac4702a269306301, a GeoJSON file
item 'Closed Trail Sections' (59,545 B), not a layer, created and modified 2024-06-23; a GIS-file
source for decision 54's second wave, 15 months stale.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'GeoJSON "Closed Trail Sections" (`26ead23c99224bdaac4702a269306301`, "Sections of LSHT System '
        'currently closed to hikers", 59,545 B, 2024-06-23), a layer of web map '
        '`661f31eba56644f09d5908a6b21ed4b8`. The Thru Hike page: "The bridge over the East Fork of the San '
        "Jacinto River at Mile 71.1 is washed out … An unmarked, unofficial, and difficult to follow detour has"
        ' been mapped".',
    ),
    where=("https://lonestartrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
