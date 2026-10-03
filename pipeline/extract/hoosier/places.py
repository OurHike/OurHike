"""Hoosier Hikers Council: places, published, and not landed (coverage audit 2026-10-01, batch
p01_persist).

Licence: attribution_only. IN DNR Properties: "…distributed 'AS-IS' without warranties… They are not
to be construed as a legal document or survey instrument… Credit should be given to the Indiana
Department of Natural Resources." DNR Recreation Sites: the same disclaimer without the credit line
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "IN DNR on `gisdata.in.gov/server/rest/services/Hosted/` (845 hosted services):",
        "`ManagedLandsAll_Live_Open_DNR_Managed/FeatureServer/1`: 671 polygons, last edit 2026-09-30, all "
        '`access_` "OPEN PER REGULATIONS". By manager: Fish and Wildlife 446, State Parks 108, Nature Preserves'
        " 67, Forestry 48. Tecumseh and Knobstone properties: Morgan-Monroe SF 5, Yellowwood SF 4, Clark SF 5, "
        "Jackson-Washington SF 3, Deam Lake SRA 1, Brown County SP 1.",
        '`ManagedLands_DNR_Open` "IN DNR Properties" (item `8ad3dd45…`, owner `dnrgis_indnr`): 654 polygons.',
        "`StateForestUnits_RO`: ForestProperty 18 …",
    ),
    where=(
        "https://gisdata.in.gov/server/rest/services/Hosted/",
        "https://hoosierhikerscouncil.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
