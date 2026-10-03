"""Roanoke Appalachian Trail Club: points of interest, published, and not landed (coverage audit
2026-10-01, batch c3_at_clubs_south).

Water reliability per shelter is what neither ATC nor `water_distance.json` carries. The capacity
disagreements are in Defects 2.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "LOADED via `atc` (code 23): shelters 16, campsites 6, privies 17, parking 22, viewpoints 81, bridges "
        "44. Not loaded: `https://www.ratc.org/at-hiking/shelter-listing/` (page; also `GET "
        "/wp-json/wp/v2/pages?slug=shelter-listing`; modified 2025-06-02) lists 16 shelters with date built, "
        "capacity, distance from A.T., water source type and distance, and reliability prose. Examples: \"Doc's "
        'Knob … one of the first to go dry each summer… often in June"; "Fullhardt Knob … the last shelter on '
        'the Appalachian Trail to use a rain cistern".',
    ),
    where=(
        "https://www.ratc.org/at-hiking/shelter-listing/",
        "https://ratc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
