"""Superior Hiking Trail Association: trail lines, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Correction 2. I chose AVAILABLE_NOT_LOADED over LOADED because about two-thirds of the trail is not
loaded and one layer holds all of it. Skeptic: re-counted `agol_sht_public` at 272 features. The
sentence "only through the Data Request form" is wrong. The SHTA's own …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "NCTA's `agol_sht_public`: 272 lines, 300.3 mi. It is partly LOADED today:",
        "via `duluth` (`duluth_superior_hiking_trail`): 67 features, about 42 mi",
        "via `usfs_trails`: 36 features, 59.8 mi; The SHTA's own geometry comes only through the Data Request "
        "form. A Lake County layer (`amy.lewis_lakecountymn` `Superior_Hiking`/3) holds 576 features.",
    ),
    where=(
        "https://utility.arcgis.com/usrsvcs/servers/085f4309eec943a8998e801f7849b1b8/rest/services",
        "https://superiorhiking.org/",
        "https://services6.arcgis.com/MoQNIarJueJ3X9ir/arcgis/rest/services/SHT_Trail_Protection_Web_Map_WFL1/FeatureServer",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
