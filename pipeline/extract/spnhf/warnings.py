"""Society for the Protection of NH Forests: warnings, published, and not landed (coverage audit
2026-10-01, batch p09_persist).

Licence: licenseInfo and copyrightText are empty on the StoryMap, the web map and the hosted layers,
so none_stated, presumed reusable under 21(a). The status and dates live in the StoryMap prose, not
the layers, and a polygon joins to its entry only by layer title (Reasoned). Whether active …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.forestsociety.org/forest-society-timber-harvests` links StoryMap "
        '`56f361b2cce140abb762bfd29a59b048` "Recent Timber Harvests" (owner a personal ArcGIS account, modified'
        ' 2026-08-31). It has 56 dated harvest entries since 2020. 2 are tagged "[Active]": Moody Mountain '
        'Forest (Wolfeboro), May 2026; Martel Forest (Goffstown), June 2026. 2 are tagged "[On Hold]". Its web '
        'map `1b41f1ac24f2475da5c72c549836f3ea` ("RecentHarvests_forStoryMap", 2026-07-06) has about 50 '
        "harvest-area layers, mostly embedded collections. 7 are hosted in the Forest Society's org "
        "`3SFpHP4jeQ4r5jD5`, e.g. …",
    ),
    where=(
        "https://www.forestsociety.org/forest-society-timber-harvests",
        "https://services8.arcgis.com/3SFpHP4jeQ4r5jD5/arcgis/rest/services/MoodyRoughHarvestShape2026/FeatureServer/0",
        "https://forestsociety.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
