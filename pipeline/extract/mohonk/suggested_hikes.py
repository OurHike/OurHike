"""Mohonk Preserve: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc).

Prose and PDF. The routes run on `mohonk_trails` names, so a name-join is plausible (Reasoned).
Skeptic additions: `/visit/trailmaps/` (`modified` 2026-09-23) adds "Maps with suggested hikes at
individual trailheads are also available for download". Guided hikes are not in WordPress at all: …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/visit/activities/suggested-hikes/` (`modified` 2026-09-24): hikes by trailhead, e.g. "
        '"Undercliff-Overcliff Loop (Via East Trapps Connector Trail)" and "Millbrook Ridge Loops", plus 5 map '
        "PDFs (`WT_SuggestedHike_AWOSTING_MAPONLY_6.19.20.pdf`, `…SKYTOP_MAP_6.14.21.pdf` ×4). `tribe_events` "
        "holds 0 events from 2026-10-01 on. `Hub Events (public)` holds 3 rows (2025-01-13).",
    ),
    where=("https://mohonkpreserve.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
