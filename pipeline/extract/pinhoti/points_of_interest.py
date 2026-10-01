"""Pinhoti Trail Alliance: points of interest, drawn from another folder's resource (coverage audit
2026-10-01, batch p02_persist).

Licence: USFS: open_licence, public domain, a federal work (`usfs_licence` in `sources.json`).
ADCNR: none_stated. Service `copyrightText` is empty and the AGOL item
`5635cb3800ae458c80c1368299f34024` has `licenseInfo: None`. Folder: `usfs` (loaded); ADCNR entrances
go in a proposed `al-dcnr` row …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`usfs_rec_sites` = "
        "`https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0`. "
        "`site_name LIKE '%PINHOTI%'` returns 10 TRAILHEAD sites, all `seasonal_operational_status='OPEN'`: "
        "Adams Gap, Bulls Gap, Porters Gap, Coleman Lake, RR Crossing, Pinky Burns, Hwy 278 (Highpoint), "
        "Cheaha, and Pinhoti #1 and #2 on Chattahoochee-Oconee. `sources.json` maps TRAILHEAD to parking, so "
        "these ship. The shelters do not ship: on National Forests in Alabama (`managing_org LIKE '0801%'`) 7 "
        'sites are named "… TRAIL SHELTER SITE" (Laurel, Oakey, Lower Shoals, Blue Mtn. …',
    ),
    where=(
        "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0",
        "https://conservationgis.alabama.gov/adcnrweb/rest/services/SPEntrances/MapServer/0",
        "https://maps.dcnr.alabama.gov/adcnrweb/rest/services",
    ),
    reason="drawn from usfs/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
