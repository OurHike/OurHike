"""Friends of the Mountains-to-Sea Trail: suggested hikes, sold or for members, behind a challenge, and not
landed (decision 54 wave 5, section K, 2026-10-04).

/the-trail/trail-guides/ (read 15:38:22Z) lists the 18 segments' guides, each 'Download Guide: Friends Members |
Non-members', the one a member's login and the other a store; the page itself states no segment's facts. A later
request (/the-trail/, 16:33:02Z) answered 202 with an SG-Captcha challenge (the header `SG-Captcha: challenge` and
a refresh to /.well-known/sgcaptcha/), which is never solved or retried. The page's contact names a staff member
with an e-mail address, never read.

The note this replaces read, whole:

Friends of the Mountains-to-Sea Trail: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Probably PDF. Not opened, because of the captcha.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Segment pages, each with "a downloadable Trail Guide" (search
snippet), and `/the-trail/trail-guides/`.

Its `where`: https://mountainstoseatrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://mountainstoseatrail.org/the-trail/trail-guides/ (HTTP 200, 182,335 bytes, 2026-10-04T15:38:22Z): 18 segments, each guide for members or for sale",
        "https://mountainstoseatrail.org/the-trail/ (HTTP 202, 181 bytes, 2026-10-04T16:33:02Z): SG-Captcha: challenge",
    ),
    where=("https://mountainstoseatrail.org/the-trail/trail-guides/",),
    reason="members only or sold: the segment guides; the host also answers a challenge (SG-Captcha), not solved",
)
