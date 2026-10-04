"""Monadnock-Sunapee Greenway Trail Club: points of interest, published with no coordinate, and not landed
(decision 54, wave 5, read live 2026-10-04).

The club's shelters page describes each Greenway shelter and tent platform in prose, with the miles between
them ("Approximately 5 miles North of the General Washington Shelter is the newly constructed Max Israel
Shelter"), and no coordinate. It names a private landowner whose house a shelter's water comes from, which
nothing here would copy. A point is never looked up from a name; needs a per-site reader, not built in this
pull request, and a fix for each shelter that a person reviews.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt (`Crawl-delay: 10`, honoured; /admin/, /wp-admin/ and the like disallowed), then /shelters/, "
        "read 2026-10-04 under lib/user_agent.py's agent: 200, 35,830 bytes; Spiltoir, Crider Forest, Fox Brook "
        "tent platform, General Washington, Max Israel, the Steve Galpin Shelter at Moose Lookout and more, in "
        "prose with miles between them; no coordinate, decimal or DDM, in the page.",
        "the coverage audit (2026-10-01, batch c4_regional_1): page only.",
    ),
    where=("https://msgtc.org/shelters/",),
    reason="needs a per-site reader, not built in this pull request: the shelters are described in prose with no coordinate",
)
