"""Georgia Appalachian Trail Club: trail lines, drawn from another folder's resource (coverage audit
2026-10-01, batch b4_oprhp_mohonk_gatc).

GATC posted on 2026-06-05 that the Byron Herbert Reece Trail was rerouted: "the old … trail was 0.8
miles long", the "new trail is 1.2 miles long", opening 2026-06-06. ATC's row reads `Length_Ft`
3,425 (0.65 mi), `GPS_Date` 2015-12-10, `Year_Built` 1968, although the layer was edited 2026-08-14.
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`ANST_Facilities/FeatureServer/6` (side trails) holds 84 rows with `Trail_Club='30'`, among them "
        '"Approach Trail", "Amicalola Falls State Park Approach Trail", "Len-Foote Hike Inn Side Trail" and '
        '"Byron H. Reece Side Trail". `APPA_Trail_Club_Sections` has 1 Georgia polygon. Not loaded: GATC\'s '
        'CalTopo map `caltopo.com/m/C02E` "Georgia Appalachian Trail" ("Appalachian Trail in Georgia with side '
        'trails and long trails which connect to the AT"). GATC\'s maps page says it "can be exported in GPX and'
        ' KML".',
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Facilities/FeatureServer/6",
        "https://caltopo.com/m/C02E",
        "https://caltopo.com/terms",
        "https://georgia-atclub.org/",
    ),
    reason="drawn from atc/trail_lines.py: ATC's side trails carry GATC's 84 `Trail_Club='30'` rows, and its "
    "centerline the A.T. in Georgia, each extracted once there (decision 34); GATC's CalTopo map has no "
    "sources.json row",
)
