"""Natural Bridge Appalachian Trail Club: challenges, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

The Blue Blazer list is the closest thing in this batch to #1780's opt-in place list. It is a PDF
table, so extracting it is a reviewed transcription, not a fetch.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Blue Blazer Program, `https://home.nbatc.org/pdfs/BlueBlazeTrailHike.pdf` (2026-07-09): a patch for "
        "hiking all 20 NBATC-maintained blue-blazed trails. Each is listed with its A.T. junction and mileage; "
        "honor system, no time limit, $5 for non-members. 88 Miler Award, `/pdfs/NBATC88milerform.pdf` "
        "(2026-08-27): complete NBATC's A.T. miles. The 100 Mile Club and Hiking Spree are members' tallies of "
        "club hikes",
    ),
    where=(
        "https://home.nbatc.org/pdfs/BlueBlazeTrailHike.pdf",
        "https://nbatc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
