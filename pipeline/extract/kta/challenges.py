"""Keystone Trails Association: challenges, a fundraiser and patches for sale, and not landed (decision 54
wave 5, section K, 2026-10-04).

The '100 Mile Challenge' is a fundraising campaign on giving.classy.org; trail patches are sold per trail through
the NeonCRM store; hiking-awards.html covers service awards.

The note this replaces read, whole:

Keystone Trails Association: challenges, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Weak: a fundraiser, not a place list (Reasoned). Skeptic spot-check, 2026-10-01: the Classy URL now 301s
to `https://giving.gofundme.com/campaign/769140/landing`: "complete 100 miles or more in Pennsylvania
between April 1 and October 31, 2026, and secure sponsorship for each mile". The separate …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "100 Mile Challenge" at
`https://giving.classy.org/campaign/769140/landing` (a fundraising hike challenge), plus trail patches
sold per trail through the NeonCRM store. `hiking-awards.html` covers service awards, not a hiker
programme.

Its `where`: https://giving.classy.org/campaign/769140/landing
https://giving.gofundme.com/campaign/769140/landing

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) https://giving.classy.org/campaign/769140/landing",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://giving.classy.org/campaign/769140/landing",),
    reason="not this type: a fundraising campaign and store patches",
)
