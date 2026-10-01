"""Mountain Club of Maryland: challenges, published, and not landed (coverage audit 2026-10-01, batch
c2_at_clubs_mid).

HAM is a dated event with registration, not an opt-in list of places. Whether it fits the challenge
shape in #1780 — Let a club publish a challenge — places on its own trails that hikers opt into and
tag at camp — starting with the ATC's A.T. Summer Bucket List is a design call (Reasoned).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Hike Across Maryland (HAM): "a 41-mile hike on the Appalachian Trail across the entire state of '
        'Maryland in a single day", held every two years (2024-05-11; gallery has HAM 2026-05-23 and Half HAM '
        '2025-10-04). Posts via WP REST. Also the "Appalachian Trail Across Maryland Hike Series" (monthly, Pen'
        " Mar → Harpers Ferry, 2025-11 → 2026-06)",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://mcomd.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
