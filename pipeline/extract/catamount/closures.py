"""Catamount Trail Association: closures, 1 notice source read here (decision 53 phase B, 2026-10-03).

- `catamount_section_31`: Catamount Trail Section 31: Jay Pass to Canadian Border, one notice,
  WordPress page 12414 through its REST route (PageNotice). The one section page of the 33 that
  carried a NOTE banner on 2026-10-01 and 2026-10-03 (active logging south of the Jay Country
  Store), read through WordPress page 12414. The other 32 section pages are not read: a banner
  posted on one of them is missed until it is registered (see catamount/closures.py).

Not read: the other 32 section pages under https://catamounttrail.org/ski-the-trail/ct-section-list/
(the parent page, WordPress id 12206). A NOTE banner can appear on any of them, and none carried one
on 2026-10-01 or 2026-10-03; one registry row a page would ask the site 33 times an hour for that. A
banner posted elsewhere is missed until its page is registered (@unvalidated: how often the club
posts one). The Green Mountain and Finger Lakes NF's alerts page
(https://www.fs.usda.gov/r09/gmfl/alerts) is the Forest Service's, read once in usfs/closures.py as
`usfs_r09_gmfl_alerts` (decision 34).

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-03 and its
measured key. The readers are extract/_notices.py's PageNotice and FeedNotices and
extract/_kinds.py's WordpressPosts. A page or a feed is read every run, one request, and is FRESH
only when what would land hashes as the last committed load did; a conditional GET is sent only
where the source's own validators were measured. A feed is a window of its newest items, never the
list of what is in force. No prose and no person lands (decisions 55 and 59).

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://anrmaps.vermont.gov/arcgis/rest/services/map_services/MAP_ANR_ANRATLASFPR_WM_NOCACHE/MapServer/3,
Vermont ANR's trail layer: 1,625 trails, every Status 'EX', so it carries no closure (a trail_lines
layer for decision 54's first wave).
"""

from extract._kinds import page_notice

CLAIMS = ("catamount_section_31",)
RESOURCES = [page_notice("catamount_section_31", wp_page=12414)]
