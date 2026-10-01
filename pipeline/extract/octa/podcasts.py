"""Oregon-California Trails Association: podcasts, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

The only org in this batch with a self-described podcast. Its RSS URL is the next thing to find

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Own: "Documentaries, YouTube, and OCTA Podcast" at `https://octa-trails.org/media/` (search index; '
        'feed URL unknown behind 403). SoundCloud `soundcloud.com/user-300818201` ("The Oregon-California '
        'Trails Association"). Upstream: `NPSAPI/multimedia/audio` oreg 8, cali 3 (exhibit audio descriptions)',
    ),
    where=(
        "https://octa-trails.org/media/",
        "https://soundcloud.com/user-300818201",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
