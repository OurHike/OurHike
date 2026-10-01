"""Randolph Mountain Club: places, published, and not landed (coverage audit 2026-10-01, batch
p05_persist).

USFS: public domain (17 U.S.C. 105). GRANIT: service copyrightText `GRANIT`, layer copyrightText
empty; AGOL item `ac1d1c9b7fb548dcaaa6bdb5c80b70d5` says "Not for legal use". That is none_stated, a
disclaimer. GRANIT's trails were retired by #1711 — Ship only hiking trails: remove NH GRANIT, and …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Loaded: `EDW_RecInfraRecreationSites_02`, managing_org 0922, has 187 TRAILHEAD sites, among them "
        "APPALACHIA, RANDOLPH PATH, LOWES PATH and LOWER FALLS (AMMO), all OPEN. `export_places.py` publishes "
        "trailhead waypoints as `kind: trailhead` places (Reasoned from its `POINT_PLACE_KINDS`). Not loaded:",
        "The WMNF boundary: `EDW_ForestSystemBoundaries_01/MapServer/0`, forestorgcode 0922.",
        "Great Gulf Wilderness: `EDW_Wilderness_02/MapServer/0`, 5,658 acres.",
        "Randolph Community Forest in GRANIT's "
        "`nhgeodata.unh.edu/nhgeodata/rest/services/EC/Conservation/MapServer/0`: 10 rows match '%Randolph%' …",
    ),
    where=("https://nhgeodata.unh.edu/nhgeodata/rest/services/EC/Conservation/MapServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
