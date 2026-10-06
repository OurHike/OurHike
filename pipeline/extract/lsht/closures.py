"""Lone Star Hiking Trail Club: closures, 1 notice source read here (decision 53 phase B, 2026-10-03).

- `lsht_thru_hike_notes`: LSHT Thru Hike page notices, one notice for the page (PageNotice). The
  club's thru-hike page, which carries 'The bridge over the East Fork of the San Jacinto River at
  Mile 71.1 is washed out' and says the Sam Houston NF's website is the official position.
  lonestartrail.org/robots.txt answers 403 to our agent, which RFC 9309 reads as unavailable (no
  restriction); the pages themselves answer 200.

The ClubExpress Terms of Use popup (https://lonestartrail.org/popup.aspx?page_id=126&club_id=738078)
answered 'Sorry - your session expired' to a cookieless request, and nothing was retried with a
session, so the club's terms are unread; both rows say so and are held for the maintainer with them.
The club defers to the Sam Houston National Forest's alerts as the official position; those are the
Forest Service's, and usfs/ does not read the Sam Houston's page (2026-10-03).

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Lone Star Hiking Trail Club: closures, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

The 2024 GeoJSON is stale-risk. The club says "the USFS website is the official position."

Restated from bcc70dd0:pipeline/reference/org_coverage.json, whose text is trimmed where it ends in '…'.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://www.arcgis.com/sharing/rest/content/items/26ead23c99224bdaac4702a269306301, a GeoJSON file
item 'Closed Trail Sections' (59,545 B), not a layer, created and modified 2024-06-23; a GIS-file
source for decision 54's second wave, 15 months stale.

Its `checked` (confirmed 2026-10-01): GeoJSON "Closed Trail Sections"
(`26ead23c99224bdaac4702a269306301`, "Sections of LSHT System currently closed to hikers", 59,545 B,
2024-06-23), a layer of web map `661f31eba56644f09d5908a6b21ed4b8`. The Thru Hike page: "The bridge
over the East Fork of the San Jacinto River at Mile 71.1 is washed out … An unmarked, unofficial,
and difficult to follow detour has been mapped".

Its `where`: https://lonestartrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import page_notice

CLAIMS = ("lsht_thru_hike_notes",)
RESOURCES = [page_notice("lsht_thru_hike_notes")]
