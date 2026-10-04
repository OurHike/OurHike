"""Colorado Fourteeners Initiative: suggested hikes, its 53 peak pages in more than one layout, and not landed
(decision 54 wave 4, section K, 2026-10-04).

14ers.org's page sitemap lists 53 /peaks/<range>/<peak>/ pages, each read 2026-10-04. They were written 2012 to
2017 in more than one layout: 23 carry a 'Recommended Route' heading whose paragraph opens with the route's name
before a dash ('Stevens Gulch Route—use of this route will help ...'), one of them (Wilson Peak's) with an update
instead; 6 of those (the Front Range's) also state an 'Elevation:' fact; 30 carry neither in a form a parser can
find. A reader for each layout is a per-site reader not built
here. The 2019 14er Report Card PDF grades routes and is the challenges or trail-condition cell's.

The note this replaces read, whole:

Colorado Fourteeners Initiative: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c5_regional_2).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The 53 peak pages each have a "Recommended Route" and route
narrative (pages, 2012–2017). `/wp-content/uploads/2019-14er-Report-Card-Combined-Final-Document.pdf`
grades 56 routes (PDF).

Its `where`: https://14ers.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.14ers.org/wp-sitemap-posts-page-1.xml (HTTP 200, 2026-10-04): 130 pages, 53 of them peaks",
        "the 53 peak pages (HTTP 200 each, 2026-10-04): 23 with a 'Recommended Route' heading, 6 of them with 'Elevation:', 30 with neither",
    ),
    where=("https://www.14ers.org/peaks/",),
    reason="needs a per-site reader, not built in this pull request: three page layouts across the 53 peaks",
)
