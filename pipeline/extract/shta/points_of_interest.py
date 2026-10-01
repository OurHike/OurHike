"""Superior Hiking Trail Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

The owner is a person, not an institution, so the layer is a lead only. Ask the SHTA (data request)
rather than take a volunteer's 2020 copy. The NCTA line layer has `camping`/`opn_camp` attributes
only. Skeptic: the SHTA's own campsites exist. The same `SHT_Trail_Protection_Web_Map_WFL1` holds:;
• …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "a personal ArcGIS account (bemidjistate org) `SHT_campsites` FeatureServer/0: 93 points, "
        'accessInformation "a named individual, SHTA Volunteer a named individual", 2020-05-05. The SHTA\'s own '
        "pages give campsite counts per sub-section, with no coordinates.",
    ),
    where=(
        "https://utility.arcgis.com/usrsvcs/servers/085f4309eec943a8998e801f7849b1b8/rest/services",
        "https://superiorhiking.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
