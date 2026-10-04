"""The Mountaineers: podcasts, refused by the host (decision 54 wave 5, section K, 2026-10-04).

mountaineers.org answers HTTP 403 to our named agent (mountaineers/suggested_hikes.py), so the 'Audio Dispatch'
(/blog/mountaineers-dispatch, a pilot that reads the club's written stories aloud, per a search) is not read. KUOW's
'The Wild' is a partner's podcast, not the club's.

The note this replaces read, whole:

The Mountaineers: podcasts, published, and not landed (coverage audit 2026-10-01, batch c5_regional_2).

Could not check the site, so this is not NOT_PUBLISHED. (Skeptic: the format, episode count and feed are
all unknown. Behind the wall it might be a Plone audio page rather than a feed.)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The search index shows only event pages for KUOW's "The Wild", a
partner's podcast. (Skeptic, 2026-10-01: a site-restricted search found "Audio Dispatch — The
Mountaineers" at `https://www.mountaineers.org/blog/mountaineers-dispatch`, described as "original
stories and perspectives from Mountaineers", and the launch post
`/blog/introducing-the-mountaineers-dispatch-listen-to-our-stories-anywhere`, which calls it "a pilot
project that brings written content to life through audio". Its series include "The Mountaineers Ascent"
("the lives, the lore, and the legends of The Mountaineers community …

Its `where`: https://www.mountaineers.org/blog/mountaineers-dispatch https://mountaineers.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=("https://www.mountaineers.org/: HTTP 403 to our agent, 2026-10-04 (mountaineers/suggested_hikes.py)",),
    where=("https://www.mountaineers.org/blog/mountaineers-dispatch",),
    reason="refused: the host answers HTTP 403 to our named agent",
)
