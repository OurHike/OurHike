"""Rocky Mountain Field Institute: podcasts, published, and not landed (coverage audit 2026-10-01,
batch c5_regional_2).

I did not find an RSS feed: the iTunes Search API returned no match on 2026-10-01, and the Spotify
page gave curl no metadata. The episode count is unknown. (Skeptic: the count is now known (3) and
the feed is still unknown. A search of iTunes for "Shovel Stories" returned 20 shows, none of them …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Shovel Stories" `https://open.spotify.com/show/47bATPBE6DoErF4Cs5fxDm`, linked from the homepage and '
        "`/media-resources`. (Skeptic, 2026-10-01: the show has its own page, "
        '`https://www.rmfi.org/shovel-stories`: "A Rocky Mountain Field Institute Podcast · Brand New for '
        '2026". It links 3 Spotify episodes, newest "Episode 3 | a named individual". Spotify\'s oEmbed and '
        "embed data date that episode 2026-08-06T15:44Z.)",
    ),
    where=(
        "https://open.spotify.com/show/47bATPBE6DoErF4Cs5fxDm",
        "https://www.rmfi.org/shovel-stories",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
