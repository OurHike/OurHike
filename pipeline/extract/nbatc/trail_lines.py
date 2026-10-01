"""Natural Bridge Appalachian Trail Club: trail lines, drawn from another folder's resource (coverage
audit 2026-10-01, batch c2_at_clubs_mid).

~~The unmatched blue-blazes may already arrive through `usfs_trails` (GWJNF), which is
Unvalidated.~~ Skeptic, 2026-10-01: settled for 7 of the 10. `usfs_trails` has Spec Mines 1.5 mi,
Hammond Hollow 1.4, Buchanan 2.6, Sulphur Spring 5.1 and Balcony Falls 5.4 (all `admin_org` 080813),
plus Henry …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "via atc `centerline`/`side_trails`. 10 of the 20 Blue Blazer trails match a name in `side_trails` "
        "(Measured; Spec Mine, Hammond Hollow, Buchanan, Sulfur Springs, Balcony Falls, Sheppe Pond, Salt Log "
        "Gap, Mount Pleasant/Henry Lanum and Flat Top did not). Own geometry: "
        "`https://home.nbatc.org/MapData/NBATC_Trails_015.kml` (49 LineStrings, A.T. segments + side trails, "
        "Last-Modified 2016-05-19), relocation KMLs (2013), `AT--MD-VA.kmz` (2013)",
    ),
    where=("https://home.nbatc.org/MapData/NBATC_Trails_015.kml",),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
