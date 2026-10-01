"""Piedmont Appalachian Trail Hikers: warnings, published, and not landed (coverage audit 2026-10-01,
batch p05_persist).

As closures. Folder `usfs/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The same page. "Fire Restrictions in place for Appalachian Trail" is not PATH\'s. Its order text limits'
        ' it to "between Beech Mountain Road (AT Milepost 489.4) and Massie Gap (AT Milepost 501 .8)", which '
        "are MRATC's miles; the loaded ATC row carries 489.4–502.4. \"Food Storage and Disposal Requirements - "
        'Bear Safety" (order 08-08-00-23-2, to 2028-08-30) lists campgrounds and recreation areas, none on '
        'PATH\'s A.T. by name. "Alcohol prohibition at the Appalachian Trail Partnership Shelter" (to '
        "2027-10-27) is a rule at a PATH shelter, not a hazard. Loaded ATC rows of category Animal or Alert in "
        "…",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://path-at.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
