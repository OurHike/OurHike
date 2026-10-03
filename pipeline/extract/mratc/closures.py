"""Mount Rogers Appalachian Trail Club: closures, 1 notice source read here (decision 53 phase B,
2026-10-03).

- `mratc_trail_alerts`: MRATC home page Trail Alerts, one notice for the page (PageNotice). The Wix
  home page's TRAIL ALERTS block (the 2026 Creeper Trail detour, VDOT lot work, FS 89 closed for
  winter), which sits in Wix's generated `comp-` elements and has no stable address, so the page's
  main region is read whole and its hash moves with anything on it. The block states no date.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Mount Rogers Appalachian Trail Club: closures, published, and not landed (coverage audit 2026-10-01,
batch c3_at_clubs_south).

ATC LOADED carries the Creeper closure and detour (`obstructs_trail: true`) and the Dickey Gap
high-water route. MRATC adds the day-hiker detail and the road and lot closures.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): The homepage block "TRAIL ALERTS" (page): the 2026 A.T. detour
during Creeper Trail reconstruction ("Most of the 20 mile detour will follow the Iron Mountain
Trail", with routing both directions), FS 89 to Whitetop closed for winter, and VDOT work on the Elk
Garden and Fox Creek lots. `/suggested-hikes` adds: "The Upper Section of the Virginia Creeper is
currently closed (from Whitetop Station to Damascus)".

Its `where`: https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services
https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services https://mratc.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from extract._kinds import page_notice

CLAIMS = ("mratc_trail_alerts",)
RESOURCES = [page_notice("mratc_trail_alerts")]
