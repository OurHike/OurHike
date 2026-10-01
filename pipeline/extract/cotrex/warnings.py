"""Colorado Parks & Wildlife — COTREX: warnings, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

These are standing conflict-area maps, not activity reports. A card must word them as "an area CPW
maps as a bear–human conflict area", never as "bear activity reported". Season dates live in
brochures (pdf), not opened.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Hunting: `CPWAdminData/6` GMU Boundary (Big Game), 186 polygons, plus "
        "`cpw.state.co.us/hunting/big-game` (page). Bears: `cpw.state.co.us/living-bears` (page). `/12` Walk In"
        " Access: 470 polygons with `CLOSEDATE`.",
        "Skeptic adds (Measured): "
        '`services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/CPWSpeciesData/FeatureServer/20` "Black '
        'Bear Human Conflict Area": 613 polygons, and `/93` "Mountain Lion Human Conflict Area": 266 polygons, '
        'both last edited 2026-05-07. The item licence reads "This wildlife distribution map is a product and '
        'property of Colorado Parks and Wildlife…".',
    ),
    where=(
        "https://cpw.state.co.us/hunting/big-game",
        "https://cpw.state.co.us/living-bears",
        "https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/CPWSpeciesData/FeatureServer/20",
        "https://services3.arcgis.com/0jWpHMuhmHsukKE3/arcgis/rest/services",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
