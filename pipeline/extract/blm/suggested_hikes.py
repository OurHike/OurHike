"""Bureau of Land Management: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch b6_federal).

Not one featured site is a hike. The hiking text is in rec-area descriptions and pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`recreation/BLM_Natl_Recreation_Sites_Facilities/MapServer/1` ("BLM Recreation Sites", 1,304): fields '
        "`RecAreaDescription`, `ActivityNames`, `BLMRecURL`. Per-site pages via `WEB_LINK`, e.g. "
        '`https://www.blm.gov/visit/black-canyon-national-recreation-trail`. "Featured Recreation Sites" '
        "(`BLM_Natl_Recreation/MapServer/12`, 74, with `TrailDifficulty` and `ElevationGainLoss`) are OHV 29, "
        "Mountain Biking 26 and Climbing 19 only.",
    ),
    where=(
        "https://www.blm.gov/visit/black-canyon-national-recreation-trail",
        "https://gis.blm.gov/arcgis/rest/services/recreation/BLM_Natl_Recreation_Sites_Facilities/MapServer/1",
        "https://gis.blm.gov/arcgis/rest/services/recreation/BLM_Natl_Recreation/MapServer/12",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
