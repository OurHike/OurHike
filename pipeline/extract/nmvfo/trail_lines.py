"""New Mexico Volunteers for the Outdoors: trail lines, drawn from another folder's resource (coverage
audit 2026-10-01, batch c6_regional_3).

The CalTopo lines are a work map, not centerlines. Use them only to place the scouting notes.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Project and scouting titles name Forest Service system trails by number, e.g. "Manzano Crest Trail '
        'FT170", "La Luz Trail FT137", "Skyline Trail FT251". Own: CalTopo map `HHBSV6V` has 58 LineString '
        "features, which are project and scouted segments.",
    ),
    where=(
        "https://coageo.cabq.gov/cabqgeo/rest/services",
        "https://nmvfo.org/",
    ),
    reason="drawn from another folder's resource, extracted once there (decision 34); checked names it",
)
