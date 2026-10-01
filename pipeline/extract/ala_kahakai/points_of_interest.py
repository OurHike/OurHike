"""Ala Kahakai Trail Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch p01_persist).

Licence: NPS public domain (federal work). Hawaii campsites public domain by state declaration
(quoted under `e-mau`). Folders: `nps-poi/`; the Hawaii state source. Kiolakaʻa's fact sheet names
"the Kapenako freshwater spring" in prose only: a water source with no coordinate, not loadable.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Along the trail: the same corridor counts as `e-mau`. NPS Public POIs 38 (KAHO 22: Restroom 4, Parking"
        " Lot 3, Entrance/Exit 4, Visitor Center 1, Ranger Station 1…). Hawaii State Parks campsites 8 (Kīholo "
        'SPR). Na Ala Hele trails 5 (amenity text, including "Potable water"). NPS ParkingLots: KAHO 1, PUHO 1,'
        " PUHE 3, ALKA 0.; On ATA's own Kaʻū lands (Waikapuna, Kaunāmano, Kāwala, Manakaʻa, Kiolakaʻa): no POI "
        "layer anywhere.",
        "`Waikapuna` 0 and `Kaunamano` 0 in AGOL.",
        "`PONC Hawaii County` 2, unrelated.",
        "County of Hawaii's 216 services include no PONC or open-space layer.",
        "County Parks …",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://alakahakaitrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
