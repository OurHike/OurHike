"""CT DEEP: suggested hikes, published as park and forest map PDFs only a person can read (decision 54 wave 4,
section K, 2026-10-04).

The trail and camping maps page links 104 PDFs, one a park or forest; the one opened (Goodwin State Forest's trail
map) is an ArcMap drawing whose text layer is its labels ('0.33 R', 'Air Line State Park Trail', '11th Section Rd')
in no reading order. The CT Rail Trail Explorer is an ArcGIS application, the lead's cell.

The note this replaces read, whole:

Connecticut DEEP: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

These are maps, not hike descriptions. Low value.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01):
`https://portal.ct.gov/deep/state-parks/trail-and-camping-maps---ct-state-parks-and-forests`: 104 unique
PDF map links, 15 with "trail" in the path. "CT Rail Trail Explorer" interactive map.

Its `where`: https://portal.ct.gov/deep/state-parks/trail-and-camping-maps---ct-state-parks-and-forests

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://portal.ct.gov/deep/state-parks/trail-and-camping-maps---ct-state-parks-and-forests (HTTP 200, 105,915 bytes, 2026-10-04T17:38:57Z): 104 PDF links",
        "goodwintrailsmappdf.pdf (HTTP 200, 3,558,105 bytes, ESRI ArcMap 10.0, 2011): one page of map labels",
    ),
    where=("https://portal.ct.gov/deep/state-parks/trail-and-camping-maps---ct-state-parks-and-forests",),
    reason="a PDF only a person can read: the park and forest maps are drawings whose mileages are map labels",
)
