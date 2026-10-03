"""Lone Star Hiking Trail Club: warnings, 1 notice source read here (decision 53 phase B, 2026-10-03).

- `lsht_news`: LSHT Club news, one notice for the page (PageNotice). The club's news list, whose one
  item on 2026-10-03 was 'DESIGNATED CAMPING IN EFFECT DURING HUNTING SEASON' (September 26, 2026 to
  January 24, 2027).

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Lone Star Hiking Trail Club: warnings, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

ClubExpress news, page only, no feed found. The hunting rule has explicit dates, so it fits the
warnings mart. Skeptic, new and stale: web map "LSHT Survey2024"
(`661f31eba56644f09d5908a6b21ed4b8`) layers a "Down Trees Labeled" WMS
(`wms.qgiscloud.com/richwinters/trees`) and a public GeoJSON …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://www.arcgis.com/sharing/rest/content/items/26ead23c99224bdaac4702a269306301, a GeoJSON file
item 'Closed Trail Sections' (59,545 B), not a layer, created and modified 2024-06-23; a GIS-file
source for decision 54's second wave, 15 months stale.

Its `checked` (confirmed 2026-10-01): News (`page_id=3`): "DESIGNATED CAMPING IN EFFECT DURING
HUNTING SEASON — Designated camping policy in effect September 26, 2026 to January 24, 2027." The
Burn Maps page (`module_id=677565`) links the R8 burn layer (Texas NFs, 386 blocks).

Its `where`: https://wms.qgiscloud.com/richwinters/trees

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import page_notice

CLAIMS = ("lsht_news",)
RESOURCES = [page_notice("lsht_news")]
