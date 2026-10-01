"""NY State Parks / NYS GIS Clearinghouse: warnings, published, and not landed (coverage audit
2026-10-01, batch b4_oprhp_mohonk_gatc).

The layer carries no season dates, so it can say "hunting happens here" but not "this week". Joining
it to DEC's statewide season calendar would be the next step. ~~The meaning of code 1 vs 2 is
@unvalidated beyond the one sample~~ (changed by skeptic: settled by the group-by this note asked
for.) …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`NY_State_Parks_Hunting_Areas_2_view/FeatureServer/1` "NYSHuntingBoundaries", polygon, 223, '
        "`dataLastEditDate` 2026-09-30 (edited the day before this audit). Field `Hunting` reads 1 on 134 and 2"
        ' on 89. The sampled code-2 row is "Restricted Area/Safety Zone", Allegany SP, 1,919.6 acres. '
        'Per-species Y/N plus coded implements (`BG_Deer_Imp` e.g. "Archery/Crossbow/Shotgun/Muzzleloader"), '
        '`WMU`, `Website`, `MasterAreaID`. The item reads "All hunting boundaries should be seen as '
        'approximate. Species, implements, and dates may be restricted". There are ~60 per-park "Hunting Parks '
        'App" web maps …',
    ),
    where=(
        "https://services.arcgis.com/1xFZPtKn1wKC6POA/arcgis/rest/services/NY_State_Parks_Hunting_Areas_2_view/FeatureServer/1",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
