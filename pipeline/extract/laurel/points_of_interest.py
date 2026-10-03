"""Laurel Highlands Hiking Trail (PA DCNR): points of interest, published, and not landed (coverage
audit 2026-10-01, batch c9_federal_state_rest).

~~No shelter-area layer exists. The LHHT's shelters, the trail's main safety feature, are in a
PDF.~~ (changed by skeptic: a point layer of all 40 shelters and 16 latrines exists. Status
unchanged; the format is ArcGIS, not PDF.) Caveats for the maintainer: it is DCNR's insurance
inventory and …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The trail map PDF, `https://elibrary.dcnr.pa.gov/GetDocument?docId=1743399&DocName=LARI_ParkMap.pdf`, "
        "shows the 8 shelter areas (per DCNR's page: five Adirondack shelters, two vault toilets and space for "
        "30 tents each). Explore PA Trails accesses (`EPAT_NEW/MapServer/0`): 2,087 statewide, 6 for LHHT, "
        "`UPDATE_` dated 2009-03-10. `Parks/State_Parks/MapServer/3`: 126 park-level amenity points. "
        "`Forestry/BOF_StateForestCampsites`: 801, all in state forests rather than on the LHHT. Skeptic find "
        "(Measured 2026-10-01): the shelters are in an ArcGIS layer. …",
    ),
    where=(
        "https://elibrary.dcnr.pa.gov/GetDocument?docId=1743399&DocName=LARI_ParkMap.pdf",
        "https://www.gis.dcnr.pa.gov/agsprod/rest/services/Parks/StateParkBuildingsMASTER/MapServer/0",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
