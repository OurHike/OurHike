"""Lone Star Hiking Trail Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

ClubExpress news, page only, no feed found. The hunting rule has explicit dates, so it fits the
warnings mart. Skeptic, new and stale: web map "LSHT Survey2024"
(`661f31eba56644f09d5908a6b21ed4b8`) layers a "Down Trees Labeled" WMS
(`wms.qgiscloud.com/richwinters/trees`) and a public GeoJSON …

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
        'News (`page_id=3`): "DESIGNATED CAMPING IN EFFECT DURING HUNTING SEASON — Designated camping policy in'
        ' effect September 26, 2026 to January 24, 2027." The Burn Maps page (`module_id=677565`) links the R8 '
        "burn layer (Texas NFs, 386 blocks).",
    ),
    where=("https://wms.qgiscloud.com/richwinters/trees",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
