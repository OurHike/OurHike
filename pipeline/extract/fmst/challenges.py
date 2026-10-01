"""Friends of the Mountains-to-Sea Trail: challenges, published, and not landed (coverage audit
2026-10-01, batch c7_regional_4).

Pages. Skeptic: the captcha still blocks curl and WebFetch (202, 202 B, on
`/challenges/40-hike-challenge/`). The search index confirms the content (R):; • the 40 Hike
Challenge is "every hike outlined in 'Great Day Hikes on North Carolina's Mountains-to-Sea Trail'",
with a patch, and its form is …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/challenges/` with:",
        "`/challenges/completing-the-entire-mst/`",
        "`/challenges/hikers-who-have-completed-the-mst/`",
        "`/challenges/40-hike-challenge/`",
        "`/challenges/junior-explorer/`",
        "`/challenges/birthday/`",
    ),
    where=("https://mountainstoseatrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
