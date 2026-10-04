"""Upper Valley Trails Alliance: suggested hikes, published as PDFs a parser cannot read reliably, and not
landed (decision 54 wave 4, section K, 2026-10-04).

'Suggested hiking venues in the Upper Valley' (2019-08-02, 13 pages) describes 12 hikes, each with its length
('1.4 miles, 440 feet'), but its text layer breaks some pages into fragments of lines (page 2 reads 'Col', 'Photos',
'Drive', 'Rew', ...), so which figure is which hike's cannot be read off it, and every hike names a contact person
with an e-mail address. The other guides (Spike Hikes, Chasing Waterfalls, Mud Season) were not opened:
uvtrails.org's robots.txt asks `Crawl-delay: 60`. Find a Trail sends hikers to Trail Finder, another site.

The note this replaces read, whole:

Upper Valley Trails Alliance: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

PDF only. Skeptic, 2026-10-01 (M): the full paths are
`wp-content/uploads/2019/09/Suggested-hiking-venues-…pdf` (a guessed `/2019/08/` path 404s), and the WP
media endpoint lists a newer `wp-content/uploads/2025/12/Spike-Hikes-Updated.pdf` (dated 2025-12-04)
beside the 2022 one.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): PDFs linked from uvtrails.org:
`Suggested-hiking-venues-in-the-Upper-Valley-2019-08-02.pdf`, `Spike-Hikes-Updated.pdf` (2022),
`Chasing-Waterfalls-Guide-0506-1.pdf` (2025-05), `Mud-Season-Guide.pdf`.

Its `where`: https://uvtrails.org

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.uvtrails.org/ (HTTP 200, 239,058 bytes, 2026-10-04): links Suggested-hiking-venues-in-the-Upper-Valley-2019-08-02.pdf, Spike-Hikes-Updated.pdf, Chasing-Waterfalls-Guide-0506-1.pdf, Mud-Season-Guide.pdf",
        "Suggested-hiking-venues-in-the-Upper-Valley-2019-08-02.pdf (HTTP 200, 1,116,496 bytes, Last-Modified 2019-09-04): page 2's text layer in fragments",
    ),
    where=("https://www.uvtrails.org/",),
    reason="a PDF only a person can read: the venues guide's text layer breaks its columns into fragments",
)
