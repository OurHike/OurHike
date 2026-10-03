"""Georgia Appalachian Trail Club: elevation, published as two PDFs of drawn profiles, not landed.

Drawn profiles, not a DEM or a table (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc). Decision 54's wave 4 parses PDFs, and keeps one that
only a person can read as a note; at most they could cross-check published
gain (`reference/published_gain.json`'s kind of evidence). USGS 3DEP
(_shared/usgs/) stays the source.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "HEAD 2026-10-03, after robots.txt (Crawl-delay 10, honoured): `wp-content/uploads/2024/11/GA-Profiles.pdf`"
        ", application/pdf, 1,192,487 bytes, and `GA-AT-Brochure-Map-Profile-2024.pdf`, 3,702,105 bytes, both "
        "Last-Modified 2024-11-21",
        "coverage audit (2026-10-01): `/for-hikers/maps/` links both",
    ),
    where=(
        "https://georgia-atclub.org/wp-content/uploads/2024/11/GA-Profiles.pdf",
        "https://georgia-atclub.org/wp-content/uploads/2024/11/GA-AT-Brochure-Map-Profile-2024.pdf",
        "https://georgia-atclub.org/",
    ),
    reason="a PDF of drawn profiles, not data: decision 54's wave 4 keeps a PDF only a person can read as a note",
)
