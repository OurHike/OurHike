"""Society for the Protection of New Hampshire Forests: challenges, the Forest Reservation Challenge's
reservations on a PDF map, and not landed (decision 54 wave 5, section K, 2026-10-04).

/challenge names the challenge's 33 featured reservations (Tier 1) and its regions (Tier 2) without listing them:
the list is a PDF game board with clickable markers (frc_game-board_0.pdf) and the Forest Reservation Guide. The
coverage audit found 33 'forest-reservation-challenge-' pages, a reader for which is not built here. The 5 Hikes
Challenge (15 August to 31 October, 25 hidden 'tree cookies') is dated. Photos participants submit 'become the
property of the Forest Society', the photos cell's business.

The note this replaces read, whole:

Society for the Protection of NH Forests: challenges, published, and not landed (coverage audit
2026-10-01, batch c4_regional_1).

Pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/challenge`: the Forest Reservation Challenge, 33 featured
reservations (33 `forest-reservation-challenge-` pages), Tier 1/2, patch and decal.
`/Fivehikeschallenge2026`: 15 Aug–31 Oct, with 25 hidden "tree cookies".

Its `where`: https://services8.arcgis.com/3SFpHP4jeQ4r5jD5/arcgis/rest/services
https://forestsociety.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.forestsociety.org/challenge (HTTP 200, 95,520 bytes, 2026-10-04): 'Visit ALL 33 of the featured reservations', the list on a PDF game board",
    ),
    where=("https://www.forestsociety.org/challenge",),
    reason="needs a per-site reader, not built in this pull request: the reservations are on a PDF map and 33 pages",
)
