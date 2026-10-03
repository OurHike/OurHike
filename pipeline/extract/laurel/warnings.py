"""Laurel Highlands Hiking Trail (PA DCNR): warnings, drawn from pasda/warnings.py's ParkAdvisory resource
(decision 53, phase B, 2026-10-03).

Laurel Ridge State Park's alerts page renders its Danger and Information sections by script from PA
DCNR's ParkAdvisory API (park id 6219), which is why the coverage audit saw them empty on
2026-10-01. That API is extracted once, in pasda/ (the folder trail_orgs.json's `via: pasda` names),
as `pa_dcnr_park_advisories`, and 6219 is on its `park_ids` against this folder. Its live IsAlert
item on 2026-10-03 is the trail's lead-contaminated tributary between mile-markers 24 and 25.

Not landed, and why: the statewide pa.gov fragment `sunday-hunting` (an AEM persisted query) ended
2025-12-07, and the inventory's reader for it waits on DCNR publishing a 2026-27 season under the
same path, which nobody has checked. Hunting season is in scope when it does. The coverage audit's
skeptic also pointed at `gis.dcnr.pa.gov/dcnrbsc/rest/services/Forestry/` for state-forest warnings,
which are ArcGIS and decision 54 wave 1's; the LHHT is state park, not state forest.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "`services.dcnr.pa.gov/ParkAddresses/api/ParkAdvisory/get?id=6219` (the decision 53 inventory, batch 1,"
        " 2026-10-03): 200, 2,425 bytes, a JSON list of 4 {IsAlert, Message}: 3 statewide (drones, spotted "
        "lanternfly, firewood) and 1 IsAlert true, 'The unnamed tributary between mile-marker 24 and 25 has been "
        "contaminated by lead and other heavy metals. Please do not use this as a drinking water source.' No "
        "title, date or id on any item. Landed by pasda/warnings.py as pa_dcnr_park_advisories.",
        "(coverage audit, 2026-10-01) The same AEM endpoint with `alertPath=…/dcnr/content-fragments/sunday-"
        'hunting`: "Sunday Hunting in State Parks", dated 2025-08-25 → 2025-12-07 (the 2025–26 season). Re-read '
        "by the inventory on 2026-10-03: unchanged, past its endDateAndTime.",
    ),
    where=(
        "https://services.dcnr.pa.gov/ParkAddresses/api/ParkAdvisory/get?id=6219",
        "https://www.pa.gov/agencies/dcnr/recreation/where-to-go/state-parks/find-a-park/laurel-ridge-state-park/alerts",
        "https://www.pa.gov/graphql/execute.json/copapwp/get-alert-by-path;alertPath=/content/dam/copapwp-pagov/en/dcnr/content-fragments/sunday-hunting",
        "https://gis.dcnr.pa.gov/dcnrbsc/rest/services/Forestry/",
    ),
    reason="drawn from pasda/'s resources, extracted once there (decision 34); checked names the layer this org's data"
    " arrives in",
)
