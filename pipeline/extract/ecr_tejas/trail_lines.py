"""El Camino Real de los Tejas NHT Association: trail lines, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`NPSAGOL/ELTE_NHT/0`: 1 line, 1:100k (2023-08-30). `nps_trails`: 0 (GUMO "Tejas Trail" is unrelated). '
        "Own: StoryMap `storymaps.arcgis.com/stories/b48d95ed5fb74f3795c587a75c524181` embedded on "
        "`/interactive-maps/`; `/georeferenced-maps/` (historic maps)",
    ),
    where=(
        "https://storymaps.arcgis.com/stories/b48d95ed5fb74f3795c587a75c524181",
        "https://elcaminorealdelostejas.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
