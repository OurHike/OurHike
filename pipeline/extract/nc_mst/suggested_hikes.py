"""NC Mountains-to-Sea Trail (NC State Trails): suggested hikes, drawn from nc_dpr/suggested_hikes.py's
`nc_parks_trails` (decision 54 wave 5, section K, 2026-10-04).

The 42 /state-parks/<park>/trails pages the coverage audit names are NC State Parks' own, on ncparks.gov, and land
once, in nc_dpr/ (decision 34).

The note this replaces read, whole:

NC Mountains-to-Sea Trail (state-published layer): suggested hikes, published, and not landed (coverage
audit 2026-10-01, batch b7_long_trails_states).

It is closer to trail attributes than to itineraries, and the blaze colour is useful.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Format page: 42 `/state-parks/<park>/trails` pages. Each holds a
table of Trail Name, Blaze, Length, Difficulty and Use, with "Export Table Data" (Crowders Mountain: 11
trails).

Its `where`: https://trails.nc.gov/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "nc_dpr/suggested_hikes.py's nc_parks_trails reads ncparks.gov/state-parks/<park>/trails, 42 pages and 407 trails, 2026-10-04",
    ),
    where=(
        "https://www.ncparks.gov/state-parks",
        "https://trails.nc.gov/",
    ),
    reason="drawn from nc_dpr/'s resource, extracted once there (decision 34); checked names the dataset this org's data arrives in",
)
