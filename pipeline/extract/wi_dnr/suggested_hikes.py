"""Wisconsin DNR: suggested hikes, its properties' hiking pages read here (decision 54 wave 5, section K,
2026-10-04).

- `wi_dnr_hiking`: the sitemap's 46 property hiking pages, found through its ten sitemap pages; the 20 that state
  each trail's length in its heading land 170 trails, each its name, property, length, shape and difficulty. The
  other 26 give the length in the department's paragraph, which is not read, and land none.

The reader is extract/_pages_content.py's ContentPages with the `wi_dnr_hiking` site parser: the rows hashed for the
change check (no page validator decides FRESH), facts and the link only, never the club's own wording. Its row in
sources.json holds the terms as found, the live read and the measured key, the property's hiking page and the
trail's name.

The note this replaces read, whole:

Wisconsin DNR Open Data: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
b7_long_trails_states).

Format page. Like NC DPR's per-park trail tables, it sits closer to trail attributes than to
itineraries, but each entry is a described hike with a length. How many properties carry the page was
not counted. `findapark` is the index to walk.

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): No hike product in the services. The per-property hiking pages on
`dnr.wisconsin.gov` were not opened. Skeptic opened one (Measured):
`dnr.wisconsin.gov/topic/parks/devilslake/recreation/hiking` (HTTP 200) lists named trails with length
and difficulty plus a sentence each, e.g. "East Bluff trail (1.7 miles) - Most difficult… passes by
Elephant Rock", "Johnson Moraine trail (2.8 miles) - Easiest", "Parfrey's Glen trail (0.7 miles)… No
food, drink or pets". A web search returned the same `/<property>/recreation/hiking` pattern for
`bluemound`, `mirrorlake`, `ngwoods` and `StateForests/nhal` …

Its `where`: https://dnr.wisconsin.gov
https://dnr.wisconsin.gov/topic/parks/devilslake/recreation/hiking
https://data-wi-dnr.opendata.arcgis.com/ https://dnrmaps.wi.gov/arcgis/rest/services

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._pages_content import content_pages

CLAIMS = ("wi_dnr_hiking",)
RESOURCES = [content_pages("wi_dnr_hiking")]
