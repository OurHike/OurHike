"""Mid State Trail Association (PA): points of interest, refused by hike-mst.org's robots.txt (decision 54, read
2026-10-04).

The association's "Selected Trailhead Parking Locations" spreadsheet (a geocoded XLS, 2016) sits under /images/,
which hike-mst.org's robots.txt disallows for every agent, ours included: `Disallow: /images/`. So it is not
fetched, and loading it is a request to the association, which the maintainer sends. The coverage audit read
it once before this rule was checked (2026-10-01: 36,352 bytes, Last-Modified 2016-08-02); nothing of that
read is kept here.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "hike-mst.org/robots.txt, read 2026-10-04T17:20:54Z under lib/user_agent.py's agent: `User-agent: *` "
        "disallows /administrator/, /cache/, /components/, /images/, /includes/ and Joomla's other folders; "
        "/images/pdfs/2016-07-01-ths-geocoded.xls falls under `Disallow: /images/`, so it was not requested.",
        "the coverage audit (2026-10-01, batch c4_regional_1): 'Selected Trailhead Parking Locations', 36,352 B, "
        "last-modified 2016-08-02, ten years old.",
    ),
    where=("https://hike-mst.org/robots.txt", "https://hike-mst.org/images/pdfs/2016-07-01-ths-geocoded.xls"),
    terms="hike-mst.org/robots.txt (read 2026-10-04): `User-agent: *` / `Disallow: /images/`",
    reason="refused: robots.txt disallows /images/, where the trailhead spreadsheet sits; held until the association permits",
)
