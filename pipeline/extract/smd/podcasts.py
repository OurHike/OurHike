"""Save Mount Diablo: podcasts, published, and not landed (coverage audit 2026-10-01, batch
c6_regional_3).

The feed is not on savemountdiablo.org, so SMD's no-automation terms do not govern it (Reasoned).
Its own "All Rights Reserved" does: link the episodes, never copy them. The producer is a named
individual and the sponsor is MDIA, so it belongs in `_shared/` podcasts (decision 12), with SMD's …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Audible Mount Diablo", RSS `https://rss.libsyn.com/shows/136346/destinations/844139.xml`. 209 '
        'episodes, 2019-02-01 → 2026-08-27. `itunes:author` is "a named individual: writer, producer", and the '
        'copyright reads "Copyright 2019, Audible Mount Diablo - All Rights Reserved." 156 of 209 episode '
        'descriptions credit SMD, usually "Sponsored by Mount Diablo Interpretive Association in partnership '
        'with Save Mount Diablo". 5 are "presented by Save Mount Diablo" (the nine-part "Harvest of Fire" '
        'series). The episodes include trail audio tours, e.g. "The Falls Trail". '
        "`/experience/online-presentations/` …",
    ),
    where=(
        "https://rss.libsyn.com/shows/136346/destinations/844139.xml",
        "https://savemountdiablo.org",
        "https://savemountdiablo.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
