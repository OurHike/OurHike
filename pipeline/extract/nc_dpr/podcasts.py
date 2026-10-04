"""NC Division of Parks & Recreation: podcasts, a feed with no episodes in it, and Spotify (decision 54
wave 3, section C, 2026-10-04).

The Ask a Ranger Podcast's SoundCloud account (soundcloud.com/ask-a-ranger, user 336243400) serves
an RSS feed with 0 items (read 2026-10-04 under our agent, HTTP 200, `<copyright>` 'All rights
reserved'), so there is nothing to land: an empty channel is a real zero, not a failed read. The
episodes are listed on Spotify, the newest 2022-10-15 (the coverage audit). NEEDS A KEY OURHIKE DOES
NOT HOLD: Spotify's show and episode lists are served only through its Web API, which needs a client
id and secret issued by Spotify at https://developer.spotify.com/dashboard; a show page is a
JavaScript client. No such credential is in the extract's environment (checked 2026-10-04), and no
RSS feed was found for the show.

The note this replaces read, whole:

NC Division of Parks & Recreation — NC Trails: podcasts, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

An ended archive, not a live feed. Spotify is the only place the episodes are listed, and Spotify is
not an open feed. Low value to a hiker.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://feeds.soundcloud.com/users/soundcloud:users:336243400/sounds.rss: HTTP 200, an RSS channel titled 'Ask a Ranger- North Carolina State Parks' with 0 items (2026-10-04); feeds.soundcloud.com's robots.txt answered 405, which RFC 9309 reads as no restriction; soundcloud.com's robots.txt allows the account page for our agent.",
        '(the coverage audit, 2026-10-01) Checked ncparks.gov and trails.nc.gov navigation, and a web search. The skeptic found the "Ask a Ranger Podcast", which Our State (`ourstate.com/talking-the-walk/`) calls "the division\'s \'Ask a Ranger Podcast\'", started in 2017 by rangers a named individual and a named individual. Spotify: `https://open.spotify.com/show/3EKATs5oSpRsU89WmW79gL` (HTTP 200). Its embed data names the newest episode "Last Episode", released 2022-10-15. SoundCloud: `https://soundcloud.com/ask-a-ranger` ("Ask a Ranger- North Carolina State Parks"). Its RSS …',
    ),
    where=(
        "https://feeds.soundcloud.com/users/soundcloud:users:336243400/sounds.rss",
        "https://soundcloud.com/ask-a-ranger",
        "https://open.spotify.com/show/3EKATs5oSpRsU89WmW79gL",
        "https://ncparks.gov",
        "https://trails.nc.gov",
        "https://ourstate.com/talking-the-walk/",
    ),
    reason="published with no episode in its feed; the episodes sit on Spotify, whose Web API needs a key OurHike does not hold",
)
