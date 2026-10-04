"""Ala Kahakai Trail Association: points of interest, published in prose with no coordinate, and not landed
(decision 54, wave 5, read live 2026-10-04).

The association's land pages describe its Kaʻū lands (Waikapuna, Kaunāmano, Kāwala, Manakaʻa, Kiolakaʻa) in
prose; Kiolakaʻa's names "the Kapenako freshwater spring" with no coordinate, so it is a water source nothing
here can place, and a point is never looked up from a name. The trail's facilities along the corridor are NPS's
and Hawaii State Parks' (the coverage audit, 2026-10-01): NPS Public POIs 38 (KAHO 22), Hawaii State Parks
campsites 8 (Kīholo SPR), Na Ala Hele trails 5. Licence, as the coverage audit read it: NPS public domain
(federal work); the Hawaii campsites public domain by state declaration (quoted under `e-mau`).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt, then /kiolokaa-kaalualu, read 2026-10-04 under lib/user_agent.py's agent: 200, 120,158 bytes "
        "(Squarespace), the land's history and a spring in prose, no coordinate in the page.",
        "the coverage audit (2026-10-01, batch p01_persist): NPS Public POIs 38 along the trail (KAHO 22: Restroom "
        "4, Parking Lot 3, Entrance/Exit 4, Visitor Center 1, Ranger Station 1); Hawaii State Parks campsites 8; "
        "on the association's own lands, no POI layer anywhere; `Waikapuna` 0 and `Kaunamano` 0 in AGOL; the "
        "County of Hawaii's 216 services include no open-space layer.",
    ),
    where=("https://alakahakaitrail.org/kiolokaa-kaalualu", "https://mapservices.nps.gov/arcgis/rest/services"),
    reason="published in prose with no coordinate: the spring and the lands are described, never placed",
)
