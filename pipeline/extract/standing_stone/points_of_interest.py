"""Standing Stone Trail Club: points of interest, published, and not landed (decision 54, wave 4, read live
2026-10-04): the water sources list is a PDF only a person can read.

"Water Sources along the Standing Stone Trail" (a 3-page Word document, made 2015-03-01) describes 32 sources
south to north in sentences ("After coming down from Cove Mountain ... Ninemile Run flows year-round"), with
no coordinate and no milepost, so placing one means reading the prose against a map, which no parser here
does. It is old: its item 4 is the Little Aughwick Creek bridge that the club's 2017 notice later closed (the
coverage audit, 2026-10-01). A HIKER'S SAFETY, in its own words: "Water supply is sporadic along the Standing
Stone Trail. Dehydration can be deadly, so plan ahead". The Sweet 16 list names 16 points (Butler Knob Shelter,
Greenwood Fire Tower and others) on a page, with no coordinates.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt (Wix's: `Allow: /`, `Disallow: *?lightbox=`, no Crawl-delay for our agent), then the water "
        "PDF whole, read 2026-10-04 under lib/user_agent.py's agent: 200, 89,416 bytes, ETag "
        '"0b8c46274ff4d4f6f8e18b84b0776729", Last-Modified 2017-02-12; pypdf\'s text is 32 numbered paragraphs '
        "of prose, no coordinate and no mile.",
        "the coverage audit (2026-10-01, batch c8_regional_5): 13 PDF maps (`/_files/ugd/30a84d_*.pdf`); the "
        "Sweet 16 page, no coordinates; `pages-sitemap.xml` (42 pages) lists `/water-sources-on-the-sst`.",
    ),
    where=("https://www.standingstonetrail.org/_files/ugd/30a84d_829f2daf5d6942c08c7f0407a2b34b28.pdf",),
    reason="a PDF only a person can read: 32 water sources in prose, with no coordinate or milepost",
)
