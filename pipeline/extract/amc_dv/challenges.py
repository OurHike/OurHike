"""AMC Delaware Valley: challenges, a bicycle challenge, and not landed (decision 54 wave 5, section K,
2026-10-04).

'Take the 2026 AMC-DV Bike Challenge!': six AMC-DV-led rides in 2026. A ride challenge is not a hiker's.

The note this replaces read, whole:

AMC Delaware Valley Chapter: challenges, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Weak. It is activity-based, bike-only and member-only, with no places, so it is out of #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with
the ATC's A.T. Summer Bucket List's shape (Reasoned), the same as `amc-berkshire`'s 150th …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): WP REST post "Take the 2026 AMC-DV Bike Challenge!",
`https://amcdv.org/activities/take-the-amc-dv-bike-challenge/` (posted 2025-02-25): "do at least six
rides with AMC-DV over 10 months in 2026", with at least one in PA, one in NJ (or DE), and one ride new
to you. Rides must be AMC-DV-led, and the challenge runs Mar 1–Dec 31, 2026, with a downloadable tally
sheet. The Spring 2026 Footnotes newsletter post also names an "AMC-DV 150 Relay".

Its `where`: https://amcdv.org/activities/take-the-amc-dv-bike-challenge/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) the WordPress post of 2025-02-25",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://amcdv.org/activities/take-the-amc-dv-bike-challenge/",),
    reason="not this type: led bicycle rides, not a list of places a hiker visits",
)
