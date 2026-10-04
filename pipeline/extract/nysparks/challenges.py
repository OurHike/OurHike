"""NY State Parks: challenges, published as dated events and a walled page, and not landed (decision 54
wave 3, section C, 2026-10-04).

THE LEAD'S RULING, 2026-10-04: "a club's dated group hike or work trip is not a suggested hike, and
not a challenge. Wire one only where its type really fits ... Otherwise it stays a dated note."

Passport Through Parks appears in OPRHP's legacy events feed
(content.parks.ny.gov/feeds/events.ashx) as dated ranger-led hikes, a sticker per hike on a set date
(the coverage audit): events, not a list of places a hiker opts into, so not a challenge. Its page
and the geocache challenge PDF answered 403 to the audit, a wall, not read past.

The note this replaces read, whole:

NY State Parks / NYS GIS Clearinghouse: challenges, published, and not landed (coverage audit
2026-10-01, batch b4_oprhp_mohonk_gatc).

Every challenge-shaped thing OPRHP runs sits on the walled-off site, apart from the feed. "Passport
Through Parks" is a list of places (every Long Island state park), but a sticker comes only from a
ranger-led hike on a set date. That is not the self-tagged, opt-in shape of #1780 — Let a club …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "The lead's ruling of 2026-10-04 on events (quoted in the docstring); no request sent today.",
        '(the coverage audit, 2026-10-01) Search index: "Passport Through Parks - New York State Parks & Historic Sites" at `parks.ny.gov/visit/events/passport-through-parks-6`. The summary says a passport book on the first hike and a sticker per hike. The page returned 403 today. Blog: "Take On The Wellness Challenge In 2025" (2025-01-07). Geocache challenges: `parks.ny.gov/documents/parks/DeltaLake2025GeocacheChallenge.pdf` (403 today).',
        '(the coverage audit, 2026-10-01) Skeptic, Measured 2026-10-01: "Passport Through Parks" is in the legacy events feed `content.parks.ny.gov/feeds/events.ashx` as 4 dated items: Cold Spring Harbor 2026-10-04, Valley Stream …',
    ),
    where=(
        "https://content.parks.ny.gov/feeds/events.ashx",
        "https://parks.ny.gov/visit/events/passport-through-parks-6",
        "https://parks.ny.gov/documents/parks/DeltaLake2025GeocacheChallenge.pdf",
    ),
    reason="not this type: dated events, which the lead ruled are not challenges (2026-10-04); the page is walled (403)",
)
