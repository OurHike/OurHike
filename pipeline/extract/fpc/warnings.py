"""Forest Park Conservancy: warnings, published, and not landed (coverage audit 2026-10-01, batch
p07_persist).

As for closures.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Portland Parks & Recreation's trail closures and delays page
(https://www.portland.gov/parks/nature/trail-closures-and-delays, 'This page was updated on
September 28, 2026', six sections, Forest Park's among them) is PP&R's, read once in
_shared/portland_parks/ as `portland_parks_trail_closures` beside its closed-assets layer (decision
34). portland.gov's robots.txt asks Crawl-delay 2.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        'The same page has 3 "Caution" entries, e.g. "Wildwood Trail at mile 15.2 - Caution: There is a stepped bypass route to the bridge… Please use caution at this temporary crossing". Tried: as for closures.',
    ),
    where=(
        "https://www.portlandmaps.com/od/rest/services",
        "https://forestparkconservancy.org/",
        "https://www.portland.gov/parks/nature/trail-closures-and-delays",
    ),
    reason="drawn from _shared/portland_parks/'s `portland_parks_trail_closures`, extracted once there (decision 34); its Caution entries are warnings",
)
