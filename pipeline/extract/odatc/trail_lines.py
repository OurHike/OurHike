"""Old Dominion Appalachian Trail Club: trail lines, drawn from another folder's resource (coverage
audit 2026-10-01, batch c2_at_clubs_mid).

The personal-account rule excludes this map. The club's homepage names "a named individual" as
co-Trail Maintenance supervisor, so it is plausibly a club officer's work map (Unvalidated). Whether
a club officer's account counts as the club's is the maintainer's call.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'via atc `centerline`; "Jack Albright Side Trail" is in `side_trails` (Measured). Own: '
        '`https://odatc.org/resources/Documents/Albright%20Loop%20Map.pdf` (PDF, 2022-02-10). ArcGIS: "ODATC '
        'Maintenance Map" (`8e11a1c016ba4f4294000646889c75a6`, 2025-06-25) and an Experience '
        "(`c178b2b8bff84d14b74d3812f207c6e7`, 2026-05-15), owned by `an email address` in the VIMS org. Its own"
        " layers: Maintenance_Sections 14, Mile_Markers 201, Current_Experience 13 lines (2022–2024), plus 2014"
        " copies of NPS layers",
    ),
    where=("https://odatc.org/resources/Documents/Albright%20Loop%20Map.pdf",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
