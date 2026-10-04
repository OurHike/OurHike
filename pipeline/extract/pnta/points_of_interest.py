"""Pacific Northwest Trail Association: points of interest, published, and not landed (decision 54, wave 4, read
live 2026-10-04): the points are symbols on an Illustrator map PDF, which only a person can read.

The 2024 overview map set's text layer repeats the legend's "Campground" and "Trail Town/ Resupply Point" on
every sheet with no coordinate; its symbols are drawings. The free 2026 Map Set is on Google Drive and was not
opened (the coverage audit, 2026-10-01). The machine-readable POIs are FarOut's, a third party's and paid.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt (Yoast's, `Disallow:` empty, no Crawl-delay), then one HEAD of the overview PDF, 2026-10-04 "
        'under lib/user_agent.py\'s agent: 200 application/pdf, 29,945,969 bytes, ETag "6839b222-1c8f071", '
        "Last-Modified 2025-05-30. Not downloaded again.",
        "the coverage audit (2026-10-01, batch c10_nst_rest): `/pnta/maps/` links 'View Overview Maps' "
        "(`/2024-section-maps-fvw/`, 301 to the PDF, Adobe Illustrator, created 2024-05-03); the 2026 Map Set "
        "(`/trail-map-download/`) is `MAPS 2026.pdf` on Google Drive, not opened.",
    ),
    where=("https://www.pnt.org/wp-content/uploads/2024/05/2024-Section-Maps-FVW.pdf", "https://pnt.org/"),
    reason="a PDF only a person can read: map symbols with no coordinate in the text layer",
)
