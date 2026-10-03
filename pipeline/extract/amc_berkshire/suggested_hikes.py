"""AMC Berkshire Chapter: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

KML is machine-readable. These are named members' lists, so check them before treating them as the
club's word.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Member Favorites" at `/favorites.cgi`: 11 Google My Maps (Accessible Trails, Berkshires, CT River '
        "Valley, Summits, Winter Trails …). Each exports KML, e.g. "
        "`https://www.google.com/maps/d/kml?mid=1RKPf6wdunmoDXSXUVgzZMZDj7z9QYMM&forcekml=1` → 200 text/xml, "
        '13,909 bytes. Also "Walking the NET" (`/walking-the-net.cgi`, a flipbook of Pioneer Valley NET '
        "descriptions).",
    ),
    where=("https://www.google.com/maps/d/kml?mid=1RKPf6wdunmoDXSXUVgzZMZDj7z9QYMM&forcekml=1",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
