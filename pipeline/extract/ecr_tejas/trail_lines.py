"""El Camino Real de los Tejas NHT Association: trail lines, drawn from nps/'s resources (decision 34),
registered on 2026-10-03.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Live read 2026-10-03 (decision 54, wave 1): `nps_el_camino_tejas_nht` (1 line) registered in "
        "sources.json and extracted in nps/trail_lines.py.",
        '`NPSAGOL/ELTE_NHT/0`: 1 line, 1:100k (2023-08-30). `nps_trails`: 0 (GUMO "Tejas Trail" is '
        "unrelated). Own: StoryMap `storymaps.arcgis.com/stories/b48d95ed5fb74f3795c587a75c524181` "
        "embedded on `/interactive-maps/`; `/georeferenced-maps/` (historic maps)",
    ),
    where=(
        "https://storymaps.arcgis.com/stories/b48d95ed5fb74f3795c587a75c524181",
        "https://elcaminorealdelostejas.org/",
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ELTE_NHT/FeatureServer/0",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
