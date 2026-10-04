"""AMC Connecticut: challenges, the East of the River Hiker Badge's 2019 form, and not landed (decision 54 wave
5, section K, 2026-10-04).

EOR_HikerBadgeForm.pdf (2019, 3 pages) lists about 27 eastern Connecticut trails, each with a source code for the
guidebook that describes it (W, the CT Walk Book; H, 50 Hikes, 1998; ...); some names wrap across lines with no
code. Its page 3 names the badge committee's members with their home addresses and telephone numbers, people's,
never read. A reader for this form is a per-family reader not built here.

The note this replaces read, whole:

AMC Connecticut Chapter: challenges, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

Settled by skeptic, 2026-10-01: "Learn more…" points to `http://ct-amc.org/eor/HikerBadge.htm`, which
returns 404. The trail list is in the form PDF
`https://ct-amc.org/wp/wp-content/uploads/2019/07/EOR_HikerBadgeForm.pdf` (143,557 bytes, last-modified
2019-07-21): 27 named trails (Bigelow Hollow …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): East of the River Hiker Badge,
`/east-of-the-river/east-of-the-river-hiker-badge/` (page, 2019): a patch for completing a designated
list of eastern CT trails.

Its `where`: https://ct-amc.org/wp/wp-content/uploads/2019/07/EOR_HikerBadgeForm.pdf https://ct-amc.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://ct-amc.org/wp/wp-content/uploads/2019/07/EOR_HikerBadgeForm.pdf (HTTP 200, 143,557 bytes, Last-Modified 2019-07-21, 2026-10-04): 3 pages",
    ),
    where=("https://ct-amc.org/wp/wp-content/uploads/2019/07/EOR_HikerBadgeForm.pdf",),
    reason="needs a per-site reader, not built in this pull request: a 2019 form whose trail names wrap",
)
