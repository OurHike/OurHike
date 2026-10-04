"""Mid State Trail Association (PA): places, refused by hike-mst.org's robots.txt (decision 54, wave 4, read
2026-10-04).

The "Mail Drop & Food Stores Table for Long Distance Backpackers" PDF sits under /images/pdfs/, which
hike-mst.org's robots.txt disallows for every agent, ours included: `Disallow: /images/`. So it is not fetched;
loading it is a request to the association, which the maintainer sends.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "hike-mst.org/robots.txt, read 2026-10-04T17:20:54Z under lib/user_agent.py's agent: `User-agent: *` "
        "disallows /images/ among Joomla's folders; /images/pdfs/mstresupplylist_2022-01-27.pdf falls under it, "
        "so it was not requested.",
        "the coverage audit (2026-10-01, batch c4_regional_1): the PDF's title, 'Mail Drop & Food Stores Table for "
        "Long Distance Backpackers'.",
    ),
    where=("https://hike-mst.org/robots.txt", "https://hike-mst.org/images/pdfs/mstresupplylist_2022-01-27.pdf"),
    terms="hike-mst.org/robots.txt (read 2026-10-04): `User-agent: *` / `Disallow: /images/`",
    reason="refused: robots.txt disallows /images/, where the resupply PDF sits; held until the association permits",
)
