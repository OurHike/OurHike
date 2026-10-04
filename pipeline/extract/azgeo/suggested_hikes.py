"""AZGeo: suggested hikes, none of its own: the Day Hiker's Guide the coverage audit names is the Arizona Trail
Association's, a download for its members only (decision 54 wave 5, section K, 2026-10-04).

aztrail.org/explore/day-hikers-guide/ says the guide splits the trail into 89 day hikes of 3.8 to 13.8 miles and
'is available as a free digital download for ATA members', and in print for $35. A members' download is not
fetched. The ATA's public passage pages are read in ata/suggested_hikes.py.

The note this replaces read, whole:

AZGeo Data Hub: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Batch c10 owns the check.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Format page: `aztrail.org/explore/day-hikers-guide/` (org_channels
2026-09-29; not reopened).

Its `where`: https://aztrail.org/explore/day-hikers-guide/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://aztrail.org/explore/day-hikers-guide/ (HTTP 200, 2026-10-04): the guide is 'available as a free digital download for ATA members'; printed copies $35 through the ATA store",
    ),
    where=("https://aztrail.org/explore/day-hikers-guide/",),
    reason="members only: the Day Hiker's Guide is a download for ATA members, which no session fetches; the public passages are ata/suggested_hikes.py's",
)
