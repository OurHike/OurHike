"""Georgia Appalachian Trail Club: challenges, published, and not landed (coverage audit 2026-10-01,
batch b4_oprhp_mohonk_gatc).

It fits #1780's shape (places a hiker opts into and tags). But several peaks are bushwhacks ("Dicks
Knob … Trail(s): Bushwhack"), so a challenge pin there invites a hiker off-trail. The card would
have to say so. The completers list is personal data and must not be loaded. Skeptic additions: the
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Georgia 4000 Challenge. `/for-hikers/georgia-4000/` (`modified` 2026-09-02): "North Georgia boasts 32 '
        'mountain peaks that are 4,000 feet or higher. Climb all 32 … and can sport our patch". '
        "`/for-hikers/georgia-4000/georgia-4000-foot-peaks/` (`modified` 2023-11-09) lists each peak with "
        'elevation, land area, trails and notes (e.g. "Brasstown Bald - 4,784 ft. Land Area: Brasstown '
        'Wilderness"). CalTopo `caltopo.com/m/0H89` "GA 4000 Challenge" ("GATC Map of 32 Georgia mountain peaks'
        " of 4000' or more elevation and 120' prominence\"). PDFs: `2023/04/Georgia_4000_Challenge.pdf` "
        "(24,189,940 bytes) and …",
    ),
    where=(
        "https://caltopo.com/m/0H89",
        "https://georgia-atclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
