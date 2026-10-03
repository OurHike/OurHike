"""Mount Rogers Appalachian Trail Club: points of interest, published, and not landed (coverage audit
2026-10-01, batch c3_at_clubs_south).

Cherry Tree Shelter is named on the 2026 official A.T. detour (MRATC homepage). Sandy Flats and
Straight Branch sit on the IMT stretch the detour uses (Reasoned from MRATC's mileages; not checked
on a map). Hikers on the detour pass shelters our map does not show.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "LOADED via `atc` (code 25): shelters 7, campsites 5, privies 12, parking 13, viewpoints 37, bridges "
        "18. Not loaded: `https://www.mratc.org/backpacking-rules` (page) lists 12 shelter and campsite rows "
        "with miles north of Damascus, bear box Y/N and privy Y/N. Three of them are on the Iron Mountain Trail"
        " and are in neither ATC's shelter layer nor USFS `usfs_rec_sites` by name: Sandy Flats Campsite (8.2 "
        "mi; bear box no, privy yes), Straight Branch Shelter (13.2 mi; no, no) and Cherry Tree Shelter (19 mi;"
        " no, yes).",
    ),
    where=("https://www.mratc.org/backpacking-rules",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
