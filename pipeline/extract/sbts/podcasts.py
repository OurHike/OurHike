"""Sierra Buttes Trail Stewardship: podcasts, published, and not landed (coverage audit 2026-10-01,
batch c6_regional_3).

A real RSS feed. The trail-report episodes double as a conditions channel (see closures). Link the
audio, never copy it, under the copyright line.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Dirt Magic", RSS `https://rss.buzzsprout.com/1119050.rss`. `itunes:author` is "Sierra Buttes Trail '
        'Stewardship", hosted by a named individual. 40 episodes, 2023-03-02 → 2026-09-04. Copyright "© 2026 '
        'Dirt Magic". Found through the Apple directory (`itunes.apple.com/search?media=podcast&term=Sierra '
        'Buttes Trail Stewardship`, 1 result). 16 of the 40 are short "Dirt Magic Trails Report" bulletins, '
        "2025-12-05 → 2026-09-04, near-weekly from March to May 2026.",
    ),
    where=(
        "https://rss.buzzsprout.com/1119050.rss",
        "https://itunes.apple.com/search?media=podcast&term=Sierra",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
