"""Washington Trails Association: points of interest, published, and not landed (decision 54, wave 5, read live
2026-10-04): one trailhead fix on each of the Hiking Guide's hike pages, which the host's Crawl-delay and the
association's terms both keep out of this pull request.

Each hike page states its trailhead's latitude and longitude (Mount Si: `latitude 47.4879799075`, the coverage
audit 2026-10-01), and the guide lists about 4,268 hikes. www.wta.org's robots.txt asks `Crawl-delay: 60` of
every agent, so one monthly read of every page is about 71 hours (4,268 x 60 s, Reasoned), far past the
monthly job's 6 hours; a reader that reads what changed since the last run, from the sitemap's lastmod, is the
shape that would fit, and is not built. The terms (quoted in `terms`) limit content to "internal informational
purposes", which decision 55 answers for notices only (facts and a link), not for a list of points; that is the
maintainer's to rule on before any reader is written.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "www.wta.org/robots.txt, read 2026-10-04 under lib/user_agent.py's agent: `User-agent: *` disallows the "
        "Plone views (`/*view$`, `/@@search` and the rest) and asks `Crawl-delay: 60`; the hike pages are allowed.",
        "the coverage audit (2026-10-01, batch c7_regional_4): one trailhead coordinate per hike page (Mount Si: "
        "`latitude 47.4879799075`); the Hiking Guide lists '4268 Hikes'.",
        "the terms, as decision 53's inventory quoted them on wta_signpost's row (2026-10-03).",
    ),
    where=(
        "https://www.wta.org/robots.txt",
        "https://www.wta.org/go-outside/hikes",
        "https://www.wta.org/our-work/about/terms-of-service",
    ),
    terms=(
        "https://www.wta.org/our-work/about/terms-of-service (decision 53's inventory, 2026-10-03): \"You may view, "
        "copy, download, and print Content that is available on this website, subject to the following conditions: "
        "The Content may be used solely for internal informational purposes. No part of this website or its Content "
        "may be reproduced or transmitted in any form, by any means, electronic or mechanical, including "
        'photocopying and recording, for any other purpose."'
    ),
    reason="needs a per-site reader that reads only changed pages at a 60 s Crawl-delay, not built in this pull request; its terms are the maintainer's to rule on first",
)
