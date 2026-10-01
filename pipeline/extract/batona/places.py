"""Batona Hiking Club: places, drawn from another folder's resource (coverage audit 2026-10-01, batch
p03_persist).

ATC: `maintainer_authorisation` (sources.json). NJDEP layers: copyrightText "NJDEP"; the Data
Distribution Agreement applies by inference from the owner (#1293). PGC: attribution_only. The
boundaries belong in `njdep/` and the PGC folder.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/AT_Communities/FeatureServer/0` has 1 "
        'point inside the "Batona Hiking Club" polygon of `APPA_Trail_Club_Sections` (OBJECTID 6): Wind Gap, '
        'PA, "Approved & Designated". In `sources.json`, `communities` carries `place_kind: town`, and '
        "`export_places.py` reads it. Not loaded: NJDEP `Open Space (State Owned) Generalized` (376 polygons, 4"
        " of them crossed by the trail). NJDEP `Open Space (State Owned) Points of Interest` (3,260 points, 23 "
        'within 200 m of the trail, including "Batona Trailhead Parking" twice, "Batona Camp", "Lower Forge …',
    ),
    where=("https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/AT_Communities/FeatureServer/0",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
