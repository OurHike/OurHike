"""Condor Trail Association: points of interest, drawn from another folder's resource (coverage audit
2026-10-01, batch p10_persist).

Licence: `usfs_rec_sites` is public domain under `usfs_licence` and is already registered. Folder:
`usfs/`. Water for the route reaches a hiker today only through `osm_water` (`_shared`, LOADED); how
many OSM springs lie on the CT is not measured (@unvalidated, settled by a buffer count against the
…

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`usfs_rec_sites` (`EDW_RecInfraRecreationSites_02/MapServer/0`) with managing_org LIKE '0507%' gives "
        "146 sites, among them TRAILHEAD 39, CAMPGROUND 63, GROUP CAMPGROUND 5, OBSERVATION SITE 3, and CAMPING"
        " AREA 5 (held back as dispersed). They ship through `export_nearby_poi.py`'s USFS_SITE_TYPES as 39 "
        'trailheads, 68 campsites and 3 viewpoints. The CT\'s northern terminus is "Botchers Gap Campground" '
        "(CTA `/maps-trail-descriptions/`), which is in the layer as BOTTCHERS GAP. No water layer: the USFS "
        "layer publishes no water site_type (its own registration says so), and no other land-manager water …",
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0",
        "https://condortrail.com/",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
