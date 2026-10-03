"""PASDA / PA DCNR: points of interest, published, and not landed (coverage audit 2026-10-01, batch
b5_nyc_nj_ct_ma_pa).

The building layer is an insurance inventory (c9). Take name, use and geometry only. `Water` on
campsites is an attribute of the site, not a water report.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Parks/StateParkBuildingsMASTER/MapServer/0` `USE1='Trail Shelter'`: 55 statewide, 40 of them the "
        "LHHT's (c9 matched those row for row to DCNR's own description). `BOF/Camping/MapServer/0` \"Designated"
        ' Campsites" (801 per c9, with a `Water` attribute Potable / Non-Potable / None per c17). '
        "`pasda/ExplorePAtrails/MapServer/2` trail access points: 3,030. `pasda/DCNR2/MapServer/27` State Park "
        "Amenities: 125. `pasda/DCNR2/MapServer/36` Geoheritage Features: 220.",
    ),
    where=(
        "https://www.gis.dcnr.pa.gov/agsprod/rest/services/Parks/StateParkBuildingsMASTER/MapServer/0",
        "https://www.gis.dcnr.pa.gov/agsprod/rest/services/BOF/Camping/MapServer/0",
        "https://mapservices.pasda.psu.edu/server/rest/services/pasda/ExplorePAtrails/MapServer/2",
        "https://mapservices.pasda.psu.edu/server/rest/services/pasda/DCNR2/MapServer/27",
        "https://mapservices.pasda.psu.edu/server/rest/services/pasda/DCNR2/MapServer/36",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
