"""DEC's own show, 'DEC Does What?!', not landed: its feed reads 'All rights reserved', and episodes would be linked, not re-hosted."""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "the show's RSS feed: 39 episodes, a few about trails (Forest Rangers, camping, the hunting season)",
        "reference/podcast_episodes.json: no episode of it",
    ),
    where=("https://feed.podbean.com/Multimedia3/feed.xml",),
    terms='the feed\'s <copyright>: "Copyright 2025 All rights reserved."',
    reason="not landed: an episode list is editorial, picked per hike in _shared/podcasts/",
)
