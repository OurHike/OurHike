"""The Trustees of Reservations: closures, nothing published (coverage audit 2026-10-01, batch
p10_persist).

NOT_AVAILABLE note for the record: "The Trustees publish closures by voicemail and Facebook (Crane
Beach page, 2026-10-01). Their ArcGIS org, their WordPress REST (including two custom namespaces),
MassGIS, DCR's alert layer, data.gov and Socrata hold no closure data." The hunting designations …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Nothing machine-readable was found. The Trustees say where their real-time channel is. The Crane Beach"
        ' page (`/place/crane-beach-on-the-crane-estate/`) reads: "Crane is no longer using Twitter (X) for '
        "real time updates. All operational updates (parking, safety, greenheads, etc.) will be posted to the "
        'Crane Beach voicemail in real time, and to our Facebook page". It also asks visitors to phone the '
        'Crane Beach information line for "the most up to date operational information" (a property line; the '
        "number is not copied). Tried: (1) The `TTOR_2` org `whFP7sXcUCogtdJz` is the only ArcGIS host …",
    ),
    where=(
        "https://data.gov",
        "https://thetrustees.org/",
        "https://thetrustees.org/wp-json/",
    ),
)
