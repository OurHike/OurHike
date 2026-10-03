"""Texas Trail Tamers: places, published, and not landed (coverage audit 2026-10-01, batch
p05_persist).

explicit_restriction, the same sentence, item `47c52b2c0edb4af0ad2c27a17b262b87`. Folder `tpwd/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`…/Texas_State_Parks_Boundaries/FeatureServer/0` has McKinney Falls, Davis Mountains and Inks Lake (3 "
        "of 116 polygons), LastEditDate 2026-03-06. The crew's other sites are private ranches and preserves. "
        "Tried: as trail_lines.",
    ),
    where=(
        "https://services1.arcgis.com/1mtXwieMId59thmg/arcgis/rest/services",
        "https://tpwd.texas.gov/arcgis/rest/services",
        "https://texastrailtamers.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
