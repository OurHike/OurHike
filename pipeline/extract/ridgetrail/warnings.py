"""Bay Area Ridge Trail Council: warnings, drawn from nps/warnings.py's NPS alerts resource (decision
53, phase B, 2026-10-03).

NPS's alerts for park code `goga` land once, in nps/warnings.py's `nps_alerts`, whose sources.json
entry lists it against this folder in `park_codes` (decision 34). NPS's Danger, Caution and
Information categories are the warnings half, split from the rest in dbt.

The inventory also found a web page, an ArcGIS layer for this club, which other phase B readers
take; if one lands for this type it takes this file, and this note becomes a line in its docstring.

The coverage audit's note, kept as it was (restated from reference/org_coverage.json, whose text is
trimmed where it ends in '…'):

Do not load: it is personal data. It is listed only so the record is complete.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://www.ebparks.org/alerts-closures (html_page).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        (
            "NPS alerts API, `parkCode=goga` (the decision 53 inventory, batch 3, 2026-10-03): 6 (Park Closure 2, "
            "Caution 2, Information 2; e.g. 'Spare the Air Alert: Fire Restrictions in Effect October 3 - 4'). "
            "31.2 Ridge Trail miles are NPS's. Landed by nps/warnings.py as nps_alerts."
        ),
        "(coverage audit, 2026-10-01) The Survey123 hazard-report layer (7 records, 2024).",
    ),
    where=(
        "https://developer.nps.gov/api/v1/alerts?parkCode=goga",
        "https://services5.arcgis.com/6iLCtMhqIxD1wlgk/arcgis/rest/services",
        "https://ridgetrail.org/",
    ),
    reason=(
        "drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in"
    ),
)
