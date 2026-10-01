"""Continental Divide Trail Coalition: places, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`Gateway_Communities_2026_view/0`: 27 points, last edit 2026-05-18. `2026_CDT_Trail_Sections_view/0`: "
        "128 sections with `Sec_Desc`. `CDT_States`.",
    ),
    where=(
        "https://services.wygisc.org/HostGIS/rest/services",
        "https://services8.arcgis.com/WyuHwdftppQLa5KO/arcgis/rest/services",
        "https://continentaldividetrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
