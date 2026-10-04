"""Washington Trails Association: suggested hikes, published, and not landed: a reader at WTA's Crawl-delay
would take hours, and its terms restrict the Content to internal use (decision 54 wave 5, section K, 2026-10-04).

wta.org/go-outside/hikes lists '4268 Hikes', each with length, elevation gain, highest point and rating, 30 a page
(`b_start:int=30` to `4260`). wta.org's robots.txt asks `Crawl-delay: 60` of every agent, so the listing alone is
143 requests, about two and a half hours, and the hike pages 71 hours (Reasoned from those two counts). WTA's Terms
of Service allow its Content to be used 'solely for internal informational purposes' (quoted in `terms`), which
restricts reuse and refuses no reading. Needs a per-site reader and a read budget that fits the monthly lane, not
built in this pull request; the terms are for the maintainer.

The note this replaces read, whole:

Washington Trails Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Pages. Trip reports are users' content and are never extracted.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/go-outside/hikes`: "4268 Hikes", each with length, elevation
gain, highest point and rating. `/go-outside/map` (Leaflet).

Its `where`: https://wta.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.wta.org/go-outside/hikes (HTTP 200, 286,082 bytes, 2026-10-04): '4268 Hikes'",
        "robots.txt (2026-10-04): `Crawl-delay: 60` under `User-agent: *`",
        "https://www.wta.org/our-work/about/terms-of-service (HTTP 200, 2026-10-04), section 3, quoted in `terms`",
    ),
    where=(
        "https://www.wta.org/go-outside/hikes",
        "https://www.wta.org/our-work/about/terms-of-service",
    ),
    terms="'You may view, copy, download, and print Content that is available on this website, subject to the following conditions: The Content may be used solely for internal informational purposes. No part of this website or its Content may be reproduced or transmitted in any form, by any means, electronic or mechanical, including photocopying and recording, for any other purpose. The Content may not be modified.'",
    reason="needs a per-site reader, not built in this pull request: 4,268 hikes, 30 a page, at a 60 s Crawl-delay need a read budget of hours, and the terms limit the Content to internal use, for the maintainer",
)
