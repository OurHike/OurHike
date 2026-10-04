"""Georgia Appalachian Trail Club: elevation, published as two PDFs of drawn profiles, not landed.

Drawn profiles, not a DEM or a table (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc), measured on 2026-10-04 (decision 54's wave 4):
GA-Profiles.pdf's five pages carry no text layer at all (2, 0, 0, 0 and 2
characters), so each profile is a picture; the brochure's one page is a
vector map whose text is its labels, places with their miles from Springer
Mountain and one elevation ("56.1 Tray Mountain 4430'"), with the profile
drawn and no figure on it. A PDF only a person can read stays a note; at
most they could cross-check published gain (`reference/published_gain.json`'s
kind of evidence). USGS 3DEP (_shared/usgs/) stays the source.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "HEAD 2026-10-03, after robots.txt (Crawl-delay 10, honoured): `wp-content/uploads/2024/11/GA-Profiles.pdf`"
        ", application/pdf, 1,192,487 bytes, and `GA-AT-Brochure-Map-Profile-2024.pdf`, 3,702,105 bytes, both "
        "Last-Modified 2024-11-21",
        "coverage audit (2026-10-01): `/for-hikers/maps/` links both",
        "GET 2026-10-04 under lib/user_agent.py's agent, Crawl-delay 10 honoured: GA-Profiles.pdf, 1,192,487 bytes, "
        'ETag "673e9cde-123227", 5 pages, pypdf text 2, 0, 0, 0 and 2 characters; the brochure, 3,702,105 bytes, '
        'ETag "673ea038-387d59", 1 page whose content stream decodes past pypdf\'s 75,000,000-byte default limit '
        "(read with the limit raised, by hand): 2,092 characters of map labels, one of them an elevation",
    ),
    where=(
        "https://georgia-atclub.org/wp-content/uploads/2024/11/GA-Profiles.pdf",
        "https://georgia-atclub.org/wp-content/uploads/2024/11/GA-AT-Brochure-Map-Profile-2024.pdf",
        "https://georgia-atclub.org/",
    ),
    reason="a PDF of drawn profiles, not data: decision 54's wave 4 keeps a PDF only a person can read as a note",
)
