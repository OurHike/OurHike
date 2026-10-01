"""Black Hills Trails: points of interest, published, and not landed (coverage audit 2026-10-01, batch
p10_persist).

Licences. LocalTrailSystem: licenseInfo empty; accessInformation and copyrightText "Black Hills
Trails, City of Sturgis". That is none_stated with a credit line, presumed reusable under 21(a). BLM
copyrightText "Bureau of Land Management, BLM, Headquarters (HQ)": open_licence, public domain as a
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://services3.arcgis.com/NbEEwwcVRO4AIaWE/arcgis/rest/services/LocalTrailSystem/FeatureServer` "
        '(item `31f9827443de4f5bbb7f2a2a74412c08`, org "City of Sturgis, SD", copyrightText "Black Hills '
        'Trails, City of Sturgis"). Layer `/0` Trailheads holds 6 points: FORT MEADE, ALKALI CREEK, DEADMAN, '
        "LIONS CLUB PARK, TILE PLANT, OLD STONE. Layer `/1` Public Parking holds 3. Last edit 2020-12-23. All "
        "three trailheads the audit found only in prose are here as points. The same org's "
        "`TrailData/FeatureServer` (item `06e039b20cf148efae08df1430b6370f`) is an older copy with 2 trailheads"
        " and 2 parking …",
    ),
    where=(
        "https://services3.arcgis.com/NbEEwwcVRO4AIaWE/arcgis/rest/services/LocalTrailSystem/FeatureServer",
        "https://services3.arcgis.com/NbEEwwcVRO4AIaWE/arcgis/rest/services/TrailData/FeatureServer",
        "https://gis.blm.gov/arcgis/rest/services/recreation/BLM_Natl_Recs_pts/MapServer",
        "https://mapservices.nps.gov/arcgis/rest/services/NationalDatasets/NPS_Public_POIs/FeatureServer/0",
        "https://tiles.arcgis.com/tiles/jWPBXspaQsJStWX8/arcgis/rest/services/Amenities_Vector/VectorTileServer",
        "https://blackhillstrails.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
