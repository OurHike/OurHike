"""Oregon Natural Desert Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Water, restricted. PDF. Skeptic: the sheet's observations are hikers' own ("Please record any water
findings you encounter"). That is water-condition data, which decision 2 keeps out of `warnings`. It
cannot be placed on a map without the gated GPX. Using it at all, even only to attach reliability …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'The guidebook\'s "water caching resources", behind the same waiver.',
        "Skeptic, new find: the ODT water chart is not behind the waiver.",
        "The ungated page `https://onda.org/discover-oregons-desert/trail-resources/water-chart-directions/` "
        "(modified 2024-06-06) links a public Google Sheet: "
        "`https://docs.google.com/spreadsheets/d/13t9UgeMj9PfTdrSo-j9MiIRXe7b8-10DFq65eJb412o/`.",
        'Its CSV export answered 200, 232,684 B. Its title row reads "Oregon Desert Trail Databook/Water Chart".',
        'It has 777 waypoint rows (`CV001`…), with mileage, elevation, landmark and "Water Details" (287 rows filled), and …',
    ),
    where=(
        "https://onda.org/discover-oregons-desert/trail-resources/water-chart-directions/",
        "https://docs.google.com/spreadsheets/d/13t9UgeMj9PfTdrSo-j9MiIRXe7b8-10DFq65eJb412o/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
