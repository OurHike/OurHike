"""Mazamas: trail lines, nothing published (coverage audit 2026-10-01, batch p04_persist).

Licence class: explicit_restriction on the page that hands out the tracks: "This information is
intended for your personal use, and it is your responsibility to confirm the accuracy of the
information." Trail lines under the club's work belong to `usfs` (already loaded as `usfs_trails`),
`oprd` and …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The only line data is off-trail climbing GPS, not trail. The `/climbroutes/` Drive folder "
        "`18VnIIbNB6q35eKR0MsVfuSly-tYUnD67` lists 50 per-peak subfolders, all dated 2018-10-03 (Big Snagtooth "
        "… Mt. Whitney). The one opened, Mt. Hood (`1fu_DIvW4dxyQcf0xZAcD4qYlw8tqB0dt`), holds 9 route "
        "subfolders: Cathedral Ridge, Coe Glacier, Leuthold Couloir, Newton Clark headwall, Sandy Headwall, ski"
        " circumnavigation, South Side, Sunshine, W'yEast. The page credits one volunteer by name; that name is"
        " not copied here. The Street Rambles page embeds a second Drive folder, "
        "`17ifkyKHMVvZSMTT55eZagCbqMNOnMIMM` …",
    ),
    where=(
        "https://mazamas.org/",
        "https://mazamas.org/arcgis/rest/services",
        "https://www3.multco.us/arcgispublic/rest/services/Countywide/PlaceswithIDs/MapServer",
    ),
)
