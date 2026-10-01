"""ATC publishes no podcast feed of its own; its one series sits on another show's feed.

Episodes reach a hiker through OurHike's own podcast desk
(_shared/podcasts/, reference/podcast_episodes.json), which picks episodes per
hike and holds the Spotify ids, rather than through a feed ATC does not own.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "'Where We Walk: Stories of the Appalachian Trail', six 2020 episodes on the She Explores feed",
        "ATC's own Where We Walk page: 404",
        "ATC's 278 pages and 328 posts: no URL names a podcast",
        "reference/podcast_episodes.json: 0 rows from that series",
    ),
    where=(
        "https://she-explores.com/podcast/where-we-walk-episode-1/",
        "https://appalachiantrail.org/explore/hike-the-a-t/where-we-walk/",
    ),
    reason="not ATC's feed: the series is on She Explores', and podcasts reach the app through _shared/podcasts/",
)
