"""NC Division of Parks & Recreation — NC Trails: podcasts, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

An ended archive, not a live feed. Spotify is the only place the episodes are listed, and Spotify is
not an open feed. Low value to a hiker.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Checked ncparks.gov and trails.nc.gov navigation, and a web search. The skeptic found the "Ask a '
        "Ranger Podcast\", which Our State (`ourstate.com/talking-the-walk/`) calls \"the division's 'Ask a "
        "Ranger Podcast'\", started in 2017 by rangers a named individual and a named individual. Spotify: "
        "`https://open.spotify.com/show/3EKATs5oSpRsU89WmW79gL` (HTTP 200). Its embed data names the newest "
        'episode "Last Episode", released 2022-10-15. SoundCloud: `https://soundcloud.com/ask-a-ranger` ("Ask a'
        ' Ranger- North Carolina State Parks"). Its RSS …',
    ),
    where=(
        "https://open.spotify.com/show/3EKATs5oSpRsU89WmW79gL",
        "https://soundcloud.com/ask-a-ranger",
        "https://ncparks.gov",
        "https://trails.nc.gov",
        "https://ourstate.com/talking-the-walk/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
