"""Oregon-California Trails Association: podcasts, drawn from nps/podcasts.py's `nps_multimedia_audio`,
and its own SoundCloud feed holds no episode (decision 54 wave 3, section C, 2026-10-04).

NPS's audio list lands once, in nps/podcasts.py, read whole, nationally, so park codes `oreg` and
`cali` are in it, and dbt assigns this folder its portion by each row's own park list matched to
nps_alerts' `park_codes` map (decision 34). OCTA's own SoundCloud account (user-300818201, user
1118106910) serves an RSS feed with 0 items (read 2026-10-04, HTTP 200, `<copyright>` 'All rights
reserved'), a real zero. octa-trails.org/media/ was not read: the coverage audit met a 403 there.

The note this replaces read, whole:

Oregon-California Trails Association: podcasts, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

The only org in this batch with a self-described podcast. Its RSS URL is the next thing to find

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "NPS /multimedia/audio (section C, 2026-10-04): landed by nps/podcasts.py as nps_multimedia_audio, national; this folder's park codes: oreg, cali.",
        "https://feeds.soundcloud.com/users/soundcloud:users:1118106910/sounds.rss: HTTP 200, a channel titled 'The Oregon-California Trails Association' with 0 items (2026-10-04).",
        '(the coverage audit, 2026-10-01) Own: "Documentaries, YouTube, and OCTA Podcast" at `https://octa-trails.org/media/` (search index; feed URL unknown behind 403). SoundCloud `soundcloud.com/user-300818201` ("The Oregon-California Trails Association"). Upstream: `NPSAPI/multimedia/audio` oreg 8, cali 3 (exhibit audio descriptions)',
    ),
    where=(
        "https://developer.nps.gov/api/v1/multimedia/audio",
        "https://feeds.soundcloud.com/users/soundcloud:users:1118106910/sounds.rss",
        "https://soundcloud.com/user-300818201",
        "https://octa-trails.org/media/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the dataset this org's data arrives in",
)
