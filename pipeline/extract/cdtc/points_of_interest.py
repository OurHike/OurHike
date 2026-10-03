"""Continental Divide Trail Coalition: points of interest, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

Water caches in the Bootheel are the difference between a dry 20 miles and not.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`CDTC_Waypoints/FeatureServer/1` Parking 81; `/2` "TH Mail" access points 292, with `PARKING`, '
        "`MAIL_L1–4`; both last edited 2026-03-03. `CDT_Water_Caches_view/0`: 7, last edit 2026-08-24. "
        "`Bootheel_Water_Caches_view/0`: 5. `Mile_Markers/0` Half_Mile_Markers: 6,155 (CC BY), last edit "
        "2026-09-30. `Post_Office_view/0`: 162. `2026_NPS_Campsites_view/1–3`: 59 (copies of NPS data, which go"
        " to `nps`).",
        "Skeptic adds: `Camping_view/FeatureServer/1`: 420 (Campsite 390, Campground 30; `UNITNAME` Yellowstone"
        " 338, Glacier 77, Rocky Mountain 5), and `NPS_Points_of_Interest_view/1`: 742. Both last edited …",
    ),
    where=(
        "https://services8.arcgis.com/WyuHwdftppQLa5KO/arcgis/rest/services/CDTC_Waypoints/FeatureServer/1",
        "https://services8.arcgis.com/WyuHwdftppQLa5KO/arcgis/rest/services/Camping_view/FeatureServer/1",
        "https://services.wygisc.org/HostGIS/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
