"""Ala Kahakai Trail Association: suggested hikes, drawn from nps/suggested_hikes.py's
`nps_things_to_do` and `nps_tours`, and dated events that are not this type (decision 54 wave 3,
section C, 2026-10-04).

NPS's things to do and tours land once, in nps/suggested_hikes.py, read whole, nationally, so park
code `alka` is in them, and dbt assigns this folder its portion (decision 34). The association's own
`/activities-and-events` collection (Squarespace, 76 items, the coverage audit) is dated walks and
talks. THE LEAD'S RULING, 2026-10-04: "a club's dated group hike or work trip is not a suggested
hike, and not a challenge. Wire one only where its type really fits ... Otherwise it stays a dated
note."

The note this replaces read, whole:

Ala Kahakai Trail Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Guided events. The upcoming/past split was empty in the JSON, so the items need the collection API

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "NPS /thingstodo and /tours (section C, 2026-10-04): landed by nps/suggested_hikes.py as nps_things_to_do and nps_tours, national; this folder's park code: alka.",
        '(the coverage audit, 2026-10-01) Own: `/activities-and-events` collection, `itemCount` 76 (Squarespace `?format=json` answers 200). `NPSAPI/tours` alka 5, incl. "Puʻuhonua — 1871 Trail" (18 stops, 1–2 h)',
    ),
    where=(
        "https://developer.nps.gov/api/v1/thingstodo",
        "https://developer.nps.gov/api/v1/tours",
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://alakahakaitrail.org/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the dataset this org's data arrives in",
)
