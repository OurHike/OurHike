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
"""

from extract._pdf_content import content_pdf

CLAIMS = ("tta_great_hikes",)
RESOURCES = [content_pdf("tta_great_hikes", crawl_delay=60.0)]
