"""MassGIS (Bureau of Geographic Information): closures, nothing published (coverage audit 2026-10-01,
batch q01_persist).

Cross-reference for `ma_dcr/`, not this row:
`services1.arcgis.com/7iJyYTjCtKsZS1LR/.../FACILITYCLOSURE_APPDATA/FeatureServer` (item `08be39f7…`,
c16: 2 rows) and `Discontinued_Quabbin_Park_Roads_and_Trails` (b5: 14).

Restated in full from the persistence pass's batch file; reference/org_coverage.json keeps a trimmed
copy.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Tried: (1) `https://arcgisserver.digital.mass.gov/arcgisserver/rest/services` re-read (the folder list"
        " now also shows `GeocodeServices`). `DFG` holds only `DFGPrintingService`; `FWE` 2 (`ILFUplandModel`, "
        "`L3ParcelsMerged`); `DCR` 2 (`Streetlights_NoEdits_Public`); `NHESP` 2; `MEMA` 2 (evacuation and "
        "inundation zones); `FEMA` 4. `PublicSafety` and `GeocodeServices` answer 502. Of the `AGOL` folder's "
        "382 services, the only names matching hunt/wild/fire/hazard/alert/closure/status are `DFW_CFR` "
        "(cold-water fisheries) and `MassWildlife_Inland_Bathymetry`. The other roots on the host "
        "(`/arcgisserver2`, `/arcgis`, `/server`, `/arcgis_image`, `/gis`, `/image`) answer 502, meaning no "
        "such root (Reasoned: the main root answered 200 the same minute). (2) AGOL `orgid:hGdibHYSPO59RG1h` "
        "(MassGIS) with closure/closed/alert/advisory/hunting/fire: 181 items, all town GIS-viewer links, `Fire"
        " Stations`, and EPA's beach viewer; no closure layer. (3) MassGIS Hub `gis.data.mass.gov` search: "
        "closure 5, closed 16, alert 7, advisory 9 (Salem Halloween road closures 2022, MassDOT CCTV, MBTA "
        'service alerts, crashes). "Discontinued Quabbin" 0, "FACILITYCLOSURE" 0, "facility closure" 0, "DCR '
        "park alerts\" 0: the clearinghouse does not catalogue DCR's closure layers. (4) Not a club, so not "
        'applicable; cross-reference below. (5) data.gov "trail closures Massachusetts" 0; Socrata "MassGIS" 1 '
        '(Somerville parcels), "DCR closure" 0. (6) `mass.gov` answers 403 (b5); not retried around. (7) No RSS'
        " reachable (mass.gov 403).",
    ),
    where=(
        "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services",
        "https://gis.data.mass.gov",
        "https://data.gov",
        "https://mass.gov",
    ),
)
