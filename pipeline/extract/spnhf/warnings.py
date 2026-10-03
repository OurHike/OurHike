"""Society for the Protection of NH Forests: warnings, published, and not landed (decision 53, phase B,
2026-10-03).

The Forest Society's active timber harvests are listed in an ArcGIS StoryMap, "Recent Timber
Harvests", and the StoryMap's item data is readable JSON (www.arcgis.com's robots.txt allows it, and
it serves an ETag, so a 304 could mark it unchanged). It is not landed, for two reasons:

- It is not a data API. The JSON is the story editor's own document, and each harvest is free text
  in a story node, "[Active] <Forest> (<town>) <month year>", with no id of its own; a reader
  would be parsing the club's prose by its tagging habit, which decision 53's readers do not do,
  and a restyled story would change the shape without changing the data.
- Whether active logging is a warning at all is the maintainer's call, open since the coverage
  audit. If it is, the harvest-area polygons in the Forest Society's own ArcGIS org (7 hosted
  layers, joinable to a story entry only by layer title, Reasoned) are the better source, and are
  decision 54 wave 1's.

The coverage audit's note (2026-10-01): licenseInfo and copyrightText are empty on the StoryMap, the
web map and the hosted layers, so none stated, presumed reusable under decision 21a. The story's
owner is a personal ArcGIS account, which nothing here records.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "`https://www.arcgis.com/sharing/rest/content/items/56f361b2cce140abb762bfd29a59b048/data?f=json` (the "
        'decision 53 inventory, batch 3, 2026-10-03): 200 application/json, 185,876 B, ETag "1a058e133c8"; item '
        "modified 2026-08-31. 3 entries tagged [Active] (Moody Mountain Forest, Wolfeboro, May 2026; Martel "
        "Forest, Goffstown, June 2026; Hills Forest & Grandpa Watson Woodlot, Madbury & Durham, July 2026, new "
        "since the audit) and 2 [On Hold] (Porter Rogerson Forest, Tamworth; Gardner Forest, Hollis), each as "
        "story-node text with no id.",
        "(coverage audit, 2026-10-01) `https://www.forestsociety.org/forest-society-timber-harvests` links the "
        "StoryMap; 56 dated harvest entries since 2020. Its web map `1b41f1ac24f2475da5c72c549836f3ea` "
        '("RecentHarvests_forStoryMap", 2026-07-06) has about 50 harvest-area layers, mostly embedded '
        "collections; 7 are hosted in the Forest Society's org `3SFpHP4jeQ4r5jD5`.",
    ),
    where=(
        "https://www.arcgis.com/sharing/rest/content/items/56f361b2cce140abb762bfd29a59b048/data?f=json",
        "https://www.forestsociety.org/forest-society-timber-harvests",
        "https://services8.arcgis.com/3SFpHP4jeQ4r5jD5/arcgis/rest/services/MoodyRoughHarvestShape2026/FeatureServer/0",
    ),
    reason=(
        "published and not landed: the StoryMap's JSON is an editor document with harvests as tagged prose, "
        "not a data API, and whether active logging is a warning is the maintainer's open question"
    ),
)
