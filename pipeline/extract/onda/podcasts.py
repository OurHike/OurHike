"""Oregon Natural Desert Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c7_regional_4).

Skeptic: `/speakerseries/` (modified 2026-03-13) offers "a recording of each event" of the 2026 High
Desert Speaker Series ("View the recording here"). These are event video recordings, not a podcast
feed. Verdict stands. (M)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('WP search for "podcast" returned 7 hits: events and staff posts, none of them a show.',),
    where=("https://onda.org/",),
)
