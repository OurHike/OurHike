"""Iditarod Historic Trail Alliance: suggested hikes, published as a visitor guide's prose, and not landed
(decision 54 wave 4, section K, 2026-10-04).

iditarod100.org/plan-your-trip.html links two PDFs; the Visitor Guide (24 pages, Adobe InDesign, 2018) is a
magazine whose regional sections (Kenai Mountains, Turnagain Arm, Anchorage Area, Wasilla Area) are prose and
photographs, with no list of hikes and their facts. Its INHT Stamp Program is the challenges cell's.

The note this replaces read, whole:

Iditarod Historic Trail Alliance: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

Prose and PDF, not routes

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `plan-your-trip.html` names the summer-usable sections (Chugach
State Park, Chugach NF, Girdwood, Eagle River). The Visitor Guide PDF has regional sections (Kenai
Mountains, Turnagain Arm, Anchorage, Wasilla)

Its `where`: https://gis.blm.gov/arcgis/rest/services
https://services2.arcgis.com/Ce3DhLRthdwbHlfF/arcgis/rest/services https://iditarod100.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.iditarod100.org/plan-your-trip.html (HTTP 200, 88,012 bytes, 2026-10-04T17:39:05Z): two PDFs, chugach-vg2015-final.pdf and iditarodnhtvisitorguide.pdf",
        "iditarodnhtvisitorguide.pdf (HTTP 200, 11,786,538 bytes, Last-Modified 2024-04-05): 24 pages, a magazine layout",
    ),
    where=("https://www.iditarod100.org/plan-your-trip.html",),
    reason="needs a per-site reader, not built in this pull request: the guide's sections are prose, not a list",
)
