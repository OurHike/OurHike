"""Mohonk Preserve: podcasts, published, and not landed (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc).

The audio tour is place-bound (12 stops on one Mohonk path), which is the shape a podcast mart
wants. It is Boulton's copyright, not Mohonk's. Metadata and links only. Skeptic spot-check: the
Spreaker feed answers 200 with 12 `<item>`s, "Stop 1: Boulder Pile in Old Pasture" to "Stop 12: Site
of the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/visit/the-trapps-mountain-hamlet-path-audio-tour/` links Apple Podcasts `id1387239867`. The iTunes "
        'lookup gives "Walk Back in Time", feed `https://www.spreaker.com/show/2957199/episodes/feed`: 12 '
        'episodes (one per stop), all 2018-05-20, `<copyright>` "Copyright a named individual". Ridgelines 222 '
        'links a "Women in Wild Places" partnership episode '
        "(`open.spotify.com/episode/4DwsE434kaBEn9vUycCkim`), a third party's show. Neither is in "
        "`reference/podcast_episodes.json` (grep).",
    ),
    where=(
        "https://www.spreaker.com/show/2957199/episodes/feed",
        "https://open.spotify.com/episode/4DwsE434kaBEn9vUycCkim",
        "https://mohonkpreserve.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
