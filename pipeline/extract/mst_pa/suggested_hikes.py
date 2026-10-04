"""Mid State Trail Association: suggested hikes, its region pages in prose, and not landed (decision 54 wave 5,
section K, 2026-10-04).

The four region pages (Everett, State College, Woolrich, Tioga) describe their sections in paragraphs ('MST
Sections 1 through 6 pass Buchanan State Forest ...') and name the regional manager with a telephone number, a
person's, never read; the section facts are the printed guide's. The region updates are notices, decision 53's.

The note this replaces read, whole:

Mid State Trail Association (PA): suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

A page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The four region pages (Everett, State College, Woolrich, Tioga)
and the section pages.

Its `where`: https://mapservices.pasda.psu.edu/server/rest/services
https://services6.arcgis.com/DtSEkvbAjAfDY35J/arcgis/rest/services https://hike-mst.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://hike-mst.org/index.php/the-trail/everett-region (HTTP 200, 37,896 bytes, 2026-10-04): 'Highlights:' and paragraphs",
    ),
    where=("https://hike-mst.org/index.php/the-trail/everett-region",),
    reason="needs a per-site reader, not built in this pull request: the regions' facts are inside paragraphs",
)
