"""Ozark Trail Association: suggested hikes, its Trail Directory's 14 sections read here (decision 54 wave 5,
section K, 2026-10-04).

- `ota_sections`: ozarktrail.com/trail-directory/ and each section's page, its miles, difficulty and ascent each
  way. Thirteen of the directory's links are '?page_id=N' redirects, which robots.txt allows. The /planner/ form's
  results were not traced and are not read.

The reader is extract/_pages_content.py's ContentPages with the `ota_sections` site parser: the rows hashed for the
change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its row in
sources.json holds the terms as found, the live read and the measured key, `link`. The terms prohibit reproduction
other than under the copyright notice, quoted on the row: a restriction on reuse, not a refusal to be read.

The note this replaces read, whole:

Ozark Trail Association: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c7_regional_4).

Pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): 14 section pages (length, difficulty, ascent, "Trail Geography"
description). `/planner/`: a trip-planner form (activity, length, pace, route type) whose result source
I did not trace.

Its `where`: https://ozarktrail.com/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("ota_sections",)
RESOURCES = [content_pages("ota_sections")]
