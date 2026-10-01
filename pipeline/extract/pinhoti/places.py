"""Pinhoti Trail Alliance: places, published, and not landed (coverage audit 2026-10-01, batch
p02_persist).

Licence: ADCNR: none_stated (empty `copyrightText`; item `licenseInfo: None`), so it is presumed
reusable under decision 21(a). Folder: a proposed `al-dcnr` row, not `pinhoti`. The Pinhoti
Experience Foundation's resupply list stays with its proposed row (audit c7).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://conservationgis.alabama.gov/adcnrweb/rest/services/StateParks/MapServer/0` has 21 state-park "
        "polygons, including Cheaha (1 match). `…/ForeverWildTracts/MapServer/0` has 228 tracts. "
        "`…/StateLands/MapServer/0` holds State Lands Division tracts. `…/DCNRTrails/MapServer/0` (566 "
        'features) holds the Pinhoti across Forever Wild land: "Pinhoti National Recreation Trail" on Weogufka '
        'State Forest Addition (6.19 mi), its Alternate Route (0.85 mi), and the "Indian Mountain Pinhoti '
        'Connector Trail" (2.48 mi). USFS forest boundaries are in `EDW_ForestSystemBoundaries_01` (not '
        "counted). Tried: as …",
    ),
    where=("https://conservationgis.alabama.gov/adcnrweb/rest/services/StateParks/MapServer/0",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
