"""Colorado Mountain Club: trail lines, nothing published (coverage audit 2026-10-01, batch
p06_persist).

No licence can be read, because every service is gated. CMC's trails are other managers' trails.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "CMC's own hosted org is gated. `services3.arcgis.com/dqi102VZf5IVARSO/arcgis/rest/services` lists 10 "
        "services (`BrainardMultiUseTrails`, `BrainardSkiOnlyTrails`, eight `R05_`). All 10 answer `499 Token "
        'Required`. The item "COTREX Trails 09_2021" is not on CMC\'s host. It is served from '
        "`services8.arcgis.com/UbfrjwJF0ZkVzVrn`, a 92-service org holding Castle Pines, CO city data (parcels,"
        " paving, plow tracks). Tried: 1 (both roots walked); 2 (`owner:CMCConservation` 31 items re-listed; "
        "Hub `Colorado Mountain Club` 23 matches, none CMC's); 3 (COTREX: `cotrex_trails` LOADED); 4 (n/a: CMC "
        "maintains …",
    ),
    where=(
        "https://services3.arcgis.com/dqi102VZf5IVARSO/arcgis/rest/services",
        "https://services8.arcgis.com/UbfrjwJF0ZkVzVrn/arcgis/rest/services",
    ),
)
