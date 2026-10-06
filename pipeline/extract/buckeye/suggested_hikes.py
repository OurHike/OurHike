"""Buckeye Trail Association: suggested hikes, its 26 section pages read here (decision 54 wave 5, section K,
2026-10-04).

- `buckeye_sections`: buckeyetrail.org/sections and each /sections/<name> page, 26 sections, each its total and
  off-road miles and its counties from the page's facts table. The table's section supervisor and contact (a
  volunteer's name, e-mail and telephone) are never read.

The reader is extract/_pages_content.py's ContentPages with the `buckeye_sections` site parser: the rows hashed for
the change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its row
in sources.json holds the terms as found, the live read and the measured key, `link`. The terms restrict downloading
and reproducing the site's content without written consent and do not forbid reading it, the reading decision 55
took for the bta_section_* notice rows; buckeye is one of the four `refuse` organizations, so nothing of this row
publishes until its permission is recorded.

The 'Hiker on the Go' maps are sold in print and are not read; /hike/circuit-hiking is prose.
"""

from extract._pages_content import content_pages

CLAIMS = ("buckeye_sections",)
RESOURCES = [content_pages("buckeye_sections")]
