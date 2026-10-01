"""Friends of the Mountains-to-Sea Trail: warnings, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The same KML's legend: \"Yellow = area and trail officially open, but trail not assessed or cleared; "
        'enter at your own risk" (0 yellow lines today). The detour pages warn of "busy roads, with sometimes '
        'narrow shoulders and limited sight lines"; Possum Track has a timber-harvest closure.',
    ),
    where=(
        "https://services7.arcgis.com/SEKZuPu27jfvDQ5b/arcgis/rest/services",
        "https://mountainstoseatrail.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
