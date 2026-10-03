"""Green Mountain Club: points of interest, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

The one layer in the batch that carries water reliability per shelter. It covers the ~170 LT-only
miles ATC does not. Honour `PublicMap = 'N'` as a withhold. Data quality: Bamforth Ridge Shelter's
`Photo1` is a privy photo.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`…/OS_MASTER/FeatureServer/0`: 72 overnight sites (47 shelters, 9 lodges, 8 camps, 8 tent sites). "
        'Fields include SH_cap, Tent_cap, Water (free text, e.g. "Unreliable spring W", "Reliable piped '
        "spring\"), Water_Srce, Water_Note, Privy_Type, Fee, Caretaker, Photo1–5, PublicMap ('N' on 1). Also "
        "`…/PARKING_MASTER` (96; Capacity, Plowed; PublicMap 'N' on 7), `…/PRIVIES_MASTER` (73), "
        "`…/VIEWPOINTS_SUMMITS_MASTER` (164; VISTA/SUMMIT/TOWER flags) and `…/MAPFEATURES_MASTER` (70). LOADED "
        "via atc (code 4): shelters 27, campsites 11, privies 32, parking 23, viewpoints 51, bridges 36.",
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services8.arcgis.com/kClE0vHJkIEmhQ53/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://greenmountainclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
