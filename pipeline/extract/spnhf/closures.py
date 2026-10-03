"""Society for the Protection of NH Forests: closures, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1; re-read by decision 53's inventory, batch 3, 2026-10-03).

Two channels, neither wired in decision 53 phase B:

- The Forest Society's OuterSpatial bulletin board
  (https://www.outerspatial.com/organizations/society-for-the-protection-of-new-hampshire-forests):
  30 cards on 2026-10-03, titles only in the HTML and no date or id per card, the embedded timestamps
  running 2020 to 2024 ('Happy Holidays ... Cheers to getting outside in 2025!'). OuterSpatial's
  robots.txt allows the page for our agent; its terms permit the site "for your personal,
  non-commercial use" and carry no automated-collection clause. Undated and stale, so a notice from
  it would be a guess at what is current: omitted rather than guessed (CLAUDE.md), and a maintainer
  call, since decision 55 would read the terms as facts and a link if it were wanted.
- https://www.forestsociety.org/forest-society-timber-harvests links the harvest StoryMap that
  warnings.py's note describes, and is not itself a notice. The property pages' free-text status
  banners (e.g. /property/mount-major-reservation) are a later per-page reader, not read.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "(decision 53 inventory, batch 3, 2026-10-03) the OuterSpatial page: 200, strong ETag; 30 bulletin cards, "
        "titles only, no visible date or id; robots.txt (User-Agent: *) disallows /profile/, /settings/, /public/, "
        "/auth/ and /geolocation/ only.",
        "`https://www.outerspatial.com/organizations/society-for-the-protection-of-new-hampshire-forests` is a "
        'public HTML page with a "Bulletin Board" of ~35 items. They include closure and opening notices ("The '
        'Rocks\' Trails & Fields Closed to Visitors for Carriage Barn Construction", "Trails are OPEN at The '
        'Rocks!"). The timestamps embedded near those items run 2020–2024, and the newest item reads "Cheers to'
        ' getting outside in 2025!". forestsociety.org itself carries free-text status banners on property '
        'pages, e.g. `/property/mount-major-reservation`: "The parking lot at Mt. Major is OPEN and the …',
    ),
    where=(
        "https://www.outerspatial.com/organizations/society-for-the-protection-of-new-hampshire-forests",
        "https://forestsociety.org",
        "https://forestsociety.org/",
    ),
    reason=(
        "published and not landed: the bulletin's cards are undated and years old, so nothing current can be "
        "told from them; the maintainer's call whether to land them as dated history"
    ),
)
