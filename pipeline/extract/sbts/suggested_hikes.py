"""Sierra Buttes Trail Stewardship: suggested hikes, none: its routes are bikepacking, motopacking and
horsepacking routes (decision 54 wave 5, section K, 2026-10-04).

/connected-communities-routes presents the Connected Communities routes by Bikepacking, Motopacking, Backpacking
and Horsepacking, the three route pages the coverage audit names all bikepacking; the Lost Sierra Recreation
Guides are magazines (PDF).

The note this replaces read, whole:

Sierra Buttes Trail Stewardship: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c6_regional_3).

Bikepacking-first, though the page names hikers too. Skeptic:
`https://www.yubaexpeditions.com/trail-routes` lists the Mt. Hough "Signature Routes" with length,
descent and climb, e.g. "Mt. Hough Trail … Length -11 Miles Descent - 4000 feet Climbing - 200 feet".
They are shuttle laps written for …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/connected-communities-routes`, plus three route pages:
`/lost-sierra-adventures-bikepacking-the-lost-sierra-loop/`,
`/bikepacking-the-lost-sierra-sagebrush-to-snowbanks/` and
`/bikepacking-the-sierra-buttes-lost-sierra-high-line/`. HTML.

Its `where`: https://www.yubaexpeditions.com/trail-routes https://sierratrails.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://sierratrails.org/connected-communities-routes (HTTP 200, 983,244 bytes, 2026-10-04T17:40:07Z): 'Bikepacking Connected Communities' and three more",
    ),
    where=("https://sierratrails.org/connected-communities-routes",),
    reason="not this type: bikepacking and motor routes, not hikes",
)
