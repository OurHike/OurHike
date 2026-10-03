"""Potomac Heritage Trail Association: trail lines, drawn from another folder's resource (coverage
audit 2026-10-01, batch c10_nst_rest).

The catalogue's "the alignment is in the NPS public trails layer" holds only inside NPS units, and
only by alternate name. The Virginia sections outside NPS land are in the association's KML
(Reasoned from its legend). No licence is stated. "Future/Advocated" lines must never render as
trail. …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Arrives via `nps` as `nps_trails`, but 0 features carry `UNITCODE='POHE'`. 446 segments carry "
        '`TRLALTNAME` like "Potomac Heritage", spread over other units: CHOH 233, GWMP 114, GRFA 33, NACE 26, '
        'ROCR 20, PRWI 17, FODU 1, OXHI 1, null 1. The association\'s own: a Google My Map "PHTA Trails" '
        "(`mid=1jTNQ94C3mkIAbXihNPY2Wk4j1_W9fPV8`, embedded at `/maps`). Its KML export "
        "`https://www.google.com/maps/d/kml?mid=…&forcekml=1` returns 200, `PHTA Trails.kml`. The legend "
        "separates Existing trail (natural surface, hard surface, sidewalk, unpaved road) from Future (planned,"
        " advocated).",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://nps.gov/pohe/",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/POHE_Trail_Centerline_FTDS_view/FeatureServer/0",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
