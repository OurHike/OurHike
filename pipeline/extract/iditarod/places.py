"""Iditarod Historic Trail Alliance: places, published as community pages with no coordinate, and not landed
(decision 54, wave 5, read 2026-10-04). About 17 community pages (Seward, Moose Pass, Girdwood ... Nome, the
coverage audit 2026-10-01) describe each trail town in prose, with no fix, and a town is never looked up from
its name. GNIS's populated places, which another folder loads, hold the same towns with fixes.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "iditarod100.org/robots.txt (/ajax/ and /apps/ disallowed), then /seward, read 2026-10-04 under "
        "lib/user_agent.py's agent: 200, 84,894 bytes, no coordinate in the page.",
        "the coverage audit (2026-10-01, batch c11_nht): about 17 community pages in the sitemap.",
    ),
    where=(
        "https://iditarod100.org/seward",
        "https://iditarod100.org/",
    ),
    reason="needs a per-site reader, not built in this pull request: trail towns described in prose, with no coordinate",
)
