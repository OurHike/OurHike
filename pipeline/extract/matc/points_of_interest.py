"""Maine Appalachian Trail Club: points of interest, drawn from another folder's resource (coverage
audit 2026-10-01, batch c1_at_clubs_north).

Not in ATC: the Grafton Loop's 4 MATC campsites, which are named on
`https://www.matc.org/grafton-loop-trail/` without coordinates. Lead: ATC's ArcGIS account
`ATConservancey` hosts a PDF `LMP_MATC_2017` (item `7ea20e7bce5943f3815316e862d5990f`).
SOURCE_SURVEY.md says the MATC plan refers to an …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("ATC layers, Trail_Club code 0: shelters 34, campsites 32, privies 51, parking 26, viewpoints 123, bridges 6.",),
    where=("https://www.matc.org/grafton-loop-trail/",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
