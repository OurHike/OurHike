"""Laurel Highlands Hiking Trail (PA DCNR): podcasts, nothing published (coverage audit 2026-10-01,
batch c9_federal_state_rest).

Verdict kept. If PPFF ever gets a catalogue row, this podcast is PPFF's, like the passport below.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Checked the LHHT page and a web search. "Hiking the Highlands" (Spotify) features a DCNR educator, but'
        " it is a third party's podcast.",
        'Skeptic re-checked: Apple\'s podcast directory, searched for "Pennsylvania DCNR", lists no show by '
        'DCNR. The nearest is "Think Outside with the Pennsylvania Parks and Forests Foundation", '
        "`https://feeds.captivate.fm/think-outside-with-ppff/` (43 episodes, newest 2026-09-23 per the "
        'directory), which features DCNR staff (e.g. "Behind the Badge: The Work of DCNR Rangers"). It is '
        "PPFF's.",
    ),
    where=("https://feeds.captivate.fm/think-outside-with-ppff/",),
)
