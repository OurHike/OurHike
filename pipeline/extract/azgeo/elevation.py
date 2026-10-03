"""AZGeo Data Hub: elevation, carried on ATA's waypoint layer, which another type registers.

The coverage audit's AZGeo elevation row (2026-10-01, batch
b7_long_trails_states) is the `Elevation` field on layer 1 of
`Arizona_National_Scenic_Trail_Feature_Layers_view`. That service is the
Arizona Trail Association's own (its ArcGIS Online organization reads
"Arizona Trail Association", 2026-10-03), which the AZGeo hub lists; this
folder already claims layer 5 of it, `azgeo_arizona_trail`. ata/elevation.py
records both elevation layers and their units (feet, measured). Whichever
folder registers layer 1 or layer 3 holds the resource, and this file becomes
`SHARES` if it is this one; one upstream is one resource (decision 34).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "layer 1, 'Arizona National Scenic Trail Points' (read 2026-10-03): 3,041 points with an integer "
        "`Elevation` field in feet (3 points, a median of 0.10 m from 3DEP through EPQS read as feet), 0 on 1 row "
        "and null on 2",
        "the service's organization, IKBBLZOXy58PXgpl, is 'Arizona Trail Association' (portals API, 2026-10-03), so "
        "the data is ATA's, listed by the hub, not AZGeo's own",
        "no other elevation product was found for AZGeo by the coverage audit (2026-10-01); not re-searched",
    ),
    where=(
        "https://services3.arcgis.com/IKBBLZOXy58PXgpl/arcgis/rest/services/Arizona_National_Scenic_Trail_Feature_Layers_view/FeatureServer/1",
        "https://azgeo-open-data-agic.hub.arcgis.com/",
    ),
    reason="carried on a layer another type's file registers: becomes SHARES once that sibling resource exists",
)
