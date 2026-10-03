"""Pacific Crest Trail Association: challenges, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

The challenge is the programme. The roster is a list of people's names and does not get loaded.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The 2,600 Miler List, `pcta.org/discover-the-trail/thru-hiking-long-distance-hiking/2600-miler-list/`:"
        " completion recognition with a medal or certificate. Found by search; the page 403s here.",
        'Skeptic adds: `pcta.org/feed/?s=2600+miler` returns the "Finishers and Alumni" page '
        "(`/discover-the-trail/thru-hiking-long-distance-hiking/alumni/`): an honour-system trail completion "
        "form, a free digital certificate, and a medal for a donation of $50 or more. Completing the form puts "
        "you on the 2600 Miler List.",
    ),
    where=(
        "https://pcta.org/discover-the-trail/thru-hiking-long-distance-hiking/2600-miler-list/",
        "https://pcta.org/feed/?s=2600+miler",
        "https://pcta.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
