"""Maah Daah Hey Trail Association: warnings, published, and not landed (coverage audit 2026-10-01,
batch q01_persist).

The unit polygons carry no season dates (`UNIT_ID`, `UNIT_TYPE`, `REGION`, `ACRES` only; items dated
2021-12), so they say which season applies, not when. NDGF's season pages were not read. Licence:
NDGF items: "The North Dakota Game and Fish Department has compiled this data according to …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

The Dakota Prairie Grasslands' alerts page (https://www.fs.usda.gov/r01/dpg/alerts, 9 alerts on
2026-10-03, the Little Missouri National Grassland's fire closure order 01-18-00-26-02 among them,
the one a hiker most needs) is the Forest Service's, read once in usfs/closures.py as
`usfs_r01_dpg_alerts`.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://services1.arcgis.com/GOcSXpzwBHyk2nog/arcgis/rest/services/NDGISHUB_Deer_Units/FeatureServer/0,
North Dakota's 39 deer units, last edited 2021-12-21, with no dates: a management geography, not a
notice.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        'Pages: `/r01/dpg/alerts`: `little-missouri-national-grassland-fire-restriction-order-01-18-00-26-08`, `north-dakota-burn-restrictions-fire-danger-maps`, `firewood-use-and-possession-restrictions`. GIS (ND GIS Hub, ND Game and Fish, `services1.arcgis.com/GOcSXpzwBHyk2nog`): `NDGISHUB_Deer_Units/0` 4B, 4C, 4D, 4E; `NDGISHUB_Elk_Units/0` E2, E3, E4; `NDGISHUB_Mountain_Lion_Units/0` 1; `NDGISHUB_Hunting_Units/0` "High Plains Unit"; `NDGISHUB_PLOTS_Lands/0` 0; `NDGISHUB_National_Grasslands/0` Little Missouri NG, McKenzie and Medora RDs. All intersect the line. BAER 0 within 1 km. Tried: (1)–(7) as …',
    ),
    where=(
        "https://services1.arcgis.com/GOcSXpzwBHyk2nog/arcgis/rest/services",
        "https://mdhta.com/",
        "https://www.fs.usda.gov/r01/dpg/alerts",
    ),
    reason="drawn from usfs/'s `usfs_r01_dpg_alerts`, extracted once there (decision 34)",
)
