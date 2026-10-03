"""Standing Stone Trail Club: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

PDF and page. The water list is 10 years old and in prose. It has to be matched to mileposts by
hand, and its item 4 describes the Little Aughwick Creek bridge that the 2017 notice (closures)
later closed.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "13 PDF maps (`/_files/ugd/30a84d_.pdf`). The Sweet 16 list names 16 points, among them Butler Knob "
        "Shelter, Greenwood Fire Tower, Monument Rock, the Thousand Steps and several vistas. It is a page, "
        "with no coordinates.",
        'Skeptic, new, water. `pages-sitemap.xml` (42 pages) lists `/water-sources-on-the-sst` ("Water Sources '
        'along the Standing Stone Trail"). It links '
        "`https://www.standingstonetrail.org/_files/ugd/30a84d_829f2daf5d6942c08c7f0407a2b34b28.pdf`: 89,416 B,"
        " 3 pages, created 2015-03-02, Last-Modified 2017-02-12. The PDF holds 32 numbered water sources, south"
        " to north, in prose with no …",
    ),
    where=("https://www.standingstonetrail.org/_files/ugd/30a84d_829f2daf5d6942c08c7f0407a2b34b28.pdf",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
