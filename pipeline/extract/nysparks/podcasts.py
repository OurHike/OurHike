"""NY State Parks / NYS GIS Clearinghouse: podcasts, nothing published (coverage audit 2026-10-01,
batch b4_oprhp_mohonk_gatc).

parks.ny.gov itself could not be read (Cloudflare), so this rests on the blog, the legacy site's
feeds and search. A re-check from a browser would harden it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Blog RSS search `nystateparks.blog/search/podcast/feed/rss2/` returns 2 posts. Neither is an OPRHP "
        'podcast: one mentions a third-party "Original People\'s Podcast" at Ganondagan. Two web searches found '
        "no OPRHP podcast, only a YouTube channel (video).",
        "Skeptic, more places checked 2026-10-01: `content.parks.ny.gov`'s home page links the blog, YouTube, "
        'Flickr, Instagram, X, Facebook and GovDelivery, and no podcast. "podcast" and "audio" match 0 of the '
        "780 events-feed items and 0 of the 10 press-release items. The one New York parks podcast search "
        'finds, "Upstate Parks and Rec" (Apple …',
    ),
    where=(
        "https://content.parks.ny.gov",
        "https://parks.ny.gov",
        "https://data.gis.ny.gov/",
    ),
)
