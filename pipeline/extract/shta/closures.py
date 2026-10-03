"""Superior Hiking Trail Association: closures, published, and not landed (coverage audit 2026-10-01,
batch c7_regional_4).

Page (HTML inside REST JSON). Reroute maps are JPG/PDF. Poll 7's `obstructs_trail` rule has to split
this one page into closures and warnings.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://superiorhiking.org/trail-conditions/`, WordPress REST page id 73, modified 2026-09-30. "
        "Organised by map series and section. Examples:",
        "the I-35 pedestrian bridge is closed, with a reroute map JPG",
        "the Spirit Mountain spur closes every winter, Nov 1–May 1",
        'the Fors Rd trailhead closed Sep 3; Also posts "Two Trail Renewal Projects Require Closures" and '
        '"Duluth SHT Closed for Fall Freeze Cycle", and the event "MN Deer Hunting Season – Trail Closures".',
    ),
    where=(
        "https://superiorhiking.org/trail-conditions/",
        "https://superiorhiking.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
