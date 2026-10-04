"""Rocky Mountain Field Institute: podcasts, published on Spotify only, and not landed (decision 54
wave 3, section C, 2026-10-04).

NEEDS A KEY OURHIKE DOES NOT HOLD: Spotify's show and episode lists are served only through its Web
API, which needs a client id and secret issued by Spotify at
https://developer.spotify.com/dashboard; a show page is a JavaScript client. No such credential is
in the extract's environment (checked 2026-10-04), and no RSS feed was found for the show.

The note this replaces read, whole:

Rocky Mountain Field Institute: podcasts, published, and not landed (coverage audit 2026-10-01,
batch c5_regional_2).

I did not find an RSS feed: the iTunes Search API returned no match on 2026-10-01, and the Spotify
page gave curl no metadata. The episode count is unknown. (Skeptic: the count is now known (3) and
the feed is still unknown. A search of iTunes for "Shovel Stories" returned 20 shows, none of them …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "Shovel Stories, rmfi.org/shovel-stories, links 3 Spotify episodes (the coverage audit's skeptic, 2026-10-01); no RSS feed URL appears on that page or the show's Spotify page (the audit); Apple's directory search was not used, because itunes.apple.com's robots.txt disallows /search* (read 2026-10-04).",
        '(the coverage audit, 2026-10-01) "Shovel Stories" `https://open.spotify.com/show/47bATPBE6DoErF4Cs5fxDm`, linked from the homepage and `/media-resources`. (Skeptic, 2026-10-01: the show has its own page, `https://www.rmfi.org/shovel-stories`: "A Rocky Mountain Field Institute Podcast · Brand New for 2026". It links 3 Spotify episodes, newest "Episode 3 | a named individual". Spotify\'s oEmbed and embed data date that episode 2026-08-06T15:44Z.)',
    ),
    where=(
        "https://www.rmfi.org/shovel-stories",
        "https://developer.spotify.com/dashboard",
        "https://open.spotify.com/show/47bATPBE6DoErF4Cs5fxDm",
    ),
    reason="needs a key OurHike does not hold: a Spotify Web API client id and secret, issued by Spotify",
)
