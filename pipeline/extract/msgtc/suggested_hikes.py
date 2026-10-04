"""Monadnock-Sunapee Greenway Trail Club: suggested hikes, published as two answers in an FAQ, and not landed
(decision 54 wave 5, section K, 2026-10-04).

msgtc.org/faq/ answers 'Best Route up or down Mount Sunapee' (the Summit Trail, 2.1 miles) and 'Best Route to
Lucia's Lookout from Pillsbury State Park' in sentences. Needs a per-site reader that reads facts out of prose, not
built in this pull request. msgtc.org asks `Crawl-delay: 10`.

The note this replaces read, whole:

Monadnock-Sunapee Greenway Trail Club: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

Thin: a page with a handful of route recommendations, not section guides. The guidebook and Super Map
are still sold. "No hike descriptions online" was too strong.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `https://www.msgtc.org/faq/`: "Best Route up or down Mount Sunapee
— We recommend taking the Summit Trail (also the SRK Trail) (2.1 miles)", "Best Route to Lucia's Lookout
from Pillsbury State Park — We recommend taking the Bear Pond Trail to the Greenway Trail north", plus
the end-to-end length note ("your hike will be about 53 miles overall").

Its `where`: https://www.msgtc.org/faq/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=("https://www.msgtc.org/faq/ (HTTP 200, 33,299 bytes, 2026-10-04): two recommended routes inside FAQ answers",),
    where=("https://www.msgtc.org/faq/",),
    reason="needs a per-site reader, not built in this pull request: two routes inside FAQ prose",
)
