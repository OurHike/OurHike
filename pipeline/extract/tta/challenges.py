"""Tennessee Trails Association: challenges, the 36 Great Hikes ('I hiked 'em all') read here (decision 54
wave 4, section K, 2026-10-04).

- `tta_great_hikes`: /wp-content/uploads/2020/08/FranWallasQualificationForm.pdf, the qualification form's 36 hikes,
  each its name as the form writes it and whether the form marks it for the state's cave ban. The form is named for
  the person the hikes honour, which no row carries. tennesseetrails.org's robots.txt asks `Crawl-delay: 60`.

The reader is extract/_pdf_content.py's ContentPdf with the `tta_great_hikes` family: a conditional GET with the
file's own validators, one row a place on the challenge's list, its facts and the link, never the club's prose and
never anyone who finished. Its row in sources.json holds the terms as found, the live read and the measured key,
`name`. The terms restrict reproducing and publishing the site's content without written permission, quoted on the
row: a restriction on reuse, not a refusal to be read.

The note this replaces read, whole:

Tennessee Trails Association: challenges, published, and not landed (coverage audit 2026-10-01, batch
c5_regional_2).

Fits the challenges mart from #1780 — Let a club publish a challenge — places on its own trails that
hikers opt into and tag at camp — starting with the ATC's A.T. Summer Bucket List, but the terms block
it.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): "a named individual Hiked 'em All": 36 hikes in TN State Parks, a
commemorative patch plus an achievement rocker, and a qualification form
`/wp-content/uploads/2020/08/FranWallasQualificationForm.pdf`. 2026 is its 15th year (HTML page).

Its `where`: https://tennesseetrails.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pdf_content import content_pdf

CLAIMS = ("tta_great_hikes",)
RESOURCES = [content_pdf("tta_great_hikes", crawl_delay=60.0)]
