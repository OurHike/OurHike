"""Tennessee Eastman Hiking & Canoeing Club: warnings, from the announcements on its club wiki and its recent
A.T. maintenance log, hourly (decision 53, phase B).

`tehcc_wiki_announcements` lands every wiki page that transcludes `Template:Announcement`, one row
per page with its latest revision's wikitext: 9 pages on 2026-10-03, among them Shelter:Iron
Mountain and Template:Watauga Area Bear Closure. An announcement has no expiry (the 2023 Watauga
bear closure looks lapsed), so each lands as a warning dated by its revision, never as a closure.
The editor's user name is never asked for.

`tehcc_recent_maintenance` reads the recent-maintenance log page
(`/trail-maintenance/recent-at-maintenance/`) as one PageNotice (extract/_notices.py), read live under
our agent on 2026-10-03: 44 reports dated 2026-08-23 to 2026-10-02 (Date, Purpose, Section, Summary).
Every report also names the people who did the work (Reporting, People); the reader lands only the
page's title, a hash of its <main> and the link, so no name reaches the raw store. The log is
generated, so WordPress page 1044's modified_gmt (2024-10-28) never moves and the row has no date.
Maintenance done, not hazards: a warning only where a summary reports an open problem.

The Appalachian Trail category of the club's WordPress posts lands in closures.py as
`tehcc_at_posts` (titles public, bodies gated and left out). Older notices the audit
listed, from those channels: "Roan Mountain Fire Restrictions extended to 2030" (2025-09-12), "Alert
– Storm Damage – North side of White Rocks" (2023-08-17), and the Chimney Top (private property,
permission needed) and Brumley Mountain Trail (parking limited to 10 vehicles) announcements, both
edited 2026-07-28. ATC's own resources carry the Roan five-year burn ban.
"""

from extract._json_apis import mediawiki_announcements
from extract._kinds import page_notice

CLAIMS = ("tehcc_wiki_announcements", "tehcc_recent_maintenance")
RESOURCES = [mediawiki_announcements("tehcc_wiki_announcements"), page_notice("tehcc_recent_maintenance")]
