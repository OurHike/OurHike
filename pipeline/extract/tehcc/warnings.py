"""Tennessee Eastman Hiking & Canoeing Club: warnings, from the announcements on its club wiki, hourly
(decision 53, phase B).

`tehcc_wiki_announcements` lands every wiki page that transcludes `Template:Announcement`, one row
per page with its latest revision's wikitext: 9 pages on 2026-10-03, among them Shelter:Iron
Mountain and Template:Watauga Area Bear Closure. An announcement has no expiry (the 2023 Watauga
bear closure looks lapsed), so each lands as a warning dated by its revision, never as a closure.
The editor's user name is never asked for.

The club's other channels the coverage audit and the inventory found are other readers': the
Appalachian Trail category of its WordPress posts (titles public, bodies gated; WordpressPosts) and
the recent-maintenance log page (`/trail-maintenance/recent-at-maintenance/`, a page reader), whose
Reporting and People columns name people and must be dropped at extract. Older notices the audit
listed, from those channels: "Roan Mountain Fire Restrictions extended to 2030" (2025-09-12), "Alert
– Storm Damage – North side of White Rocks" (2023-08-17), and the Chimney Top (private property,
permission needed) and Brumley Mountain Trail (parking limited to 10 vehicles) announcements, both
edited 2026-07-28. ATC's own resources carry the Roan five-year burn ban.
"""

from extract._json_apis import mediawiki_announcements

CLAIMS = ("tehcc_wiki_announcements",)
RESOURCES = [mediawiki_announcements("tehcc_wiki_announcements")]
