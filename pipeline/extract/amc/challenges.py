"""Appalachian Mountain Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

A peak list, which is the #1780 shape. No machine-readable peak coordinates were found. Skeptic,
confirmed: `amc4000footer.org/` 302s to `/the-lists-we-recognize.html`. That page links the list
pages and `/ne-111-list-of-peaks.pdf` (PDF), and its one StoryMap link is AMC's All Out: AMC Action
Plan …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "AMC Four Thousand Footer Committee, `https://www.amc4000footer.org/`: 4 lists (White Mountain "
        "4000-Footers, NE 4000-Footers, NE Hundred Highest, NE111), applications as PDF (e.g. "
        "`/Appz/App%20AMC%20WM4000.pdf`), fee $10–15. NET Hike Challenge 2026 (with CFPA).",
    ),
    where=(
        "https://www.amc4000footer.org/",
        "https://amc4000footer.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
