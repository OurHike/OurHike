"""The Trustees of Reservations: trail lines, published as per-property trail map PDFs, and not landed (decision
54, wave 4, read live 2026-10-04): a drawn map is a PDF only a person can read here.

Each property's trail map is a PDF (Notchview's, at 1,576,956 bytes), whose lines are artwork, and a "Mobile
Map" through Avenza, a third party's app. No vector trail layer is in the Trustees' own GIS (`TTOR_2`: searches
for trail, trails, parking and amenities found only coastal, grassland and Bay Circuit items, the coverage audit
2026-10-01), and massgis' trails do not carry them (the coverage audit's corrections 2 and 3).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt (Yoast's, `Disallow:` empty), then one HEAD of Notchview's trail map, 2026-10-04 under "
        "lib/user_agent.py's agent: https://thetrustees.org/wp-content/uploads/2024/07/notchview-trail-map.pdf, "
        '200 application/pdf, 1,576,956 bytes, ETag "6998c6af-180ffc", Last-Modified 2026-02-20 (the 2020 URL '
        "the coverage audit read now 301s there).",
        "the coverage audit (2026-10-01, batch c4_regional_1): no vector trail layer in `TTOR_2`; 'Notchview "
        "Mobile Map' via Avenza; not LOADED via massgis (corrections 2 and 3).",
    ),
    where=("https://thetrustees.org/wp-content/uploads/2024/07/notchview-trail-map.pdf",),
    reason="a PDF only a person can read: the trail maps are drawn, with no vector line a parser can take",
)
