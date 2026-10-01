"""Mount Rogers Appalachian Trail Club: closures, published, and not landed (coverage audit 2026-10-01,
batch c3_at_clubs_south).

ATC LOADED carries the Creeper closure and detour (`obstructs_trail: true`) and the Dickey Gap
high-water route. MRATC adds the day-hiker detail and the road and lot closures.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The homepage block "TRAIL ALERTS" (page): the 2026 A.T. detour during Creeper Trail reconstruction '
        '("Most of the 20 mile detour will follow the Iron Mountain Trail", with routing both directions), FS '
        "89 to Whitetop closed for winter, and VDOT work on the Elk Garden and Fox Creek lots. "
        '`/suggested-hikes` adds: "The Upper Section of the Virginia Creeper is currently closed (from Whitetop'
        ' Station to Damascus)".',
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://mratc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
