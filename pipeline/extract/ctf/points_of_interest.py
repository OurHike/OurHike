"""Colorado Trail Foundation: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

GPX from a third party, not the CTF. ~~"WT" may mean water, which nobody here has checked~~.
Skeptic, settled: `http://bearcreeksurvey.com/Data/Mapbook_Prefaces.pdf` (460,484 B, last-modified
2017-07-23) says: "WT= Water - found in dry year 2014. WS= Seasonal Water. WR= Hiker reported water
sources …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Bear Creek Survey, the CTF's pro-bono surveyor and Map Book cartographer: "
        "`http://bearcreeksurvey.com/Data/CT_2020_GPX.zip` (20,583 B, 2020-02-06). 881 waypoints with letter "
        "codes (e.g. `01-033WT`, 261 `WT`-suffixed). The coding is explained in `Data/Mapbook_Prefaces.pdf`.",
    ),
    where=(
        "https://services3.arcgis.com/0jWpHMuhmHsukKE3/arcgis/rest/services",
        "https://coloradotrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
