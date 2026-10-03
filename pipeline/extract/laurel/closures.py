"""Laurel Highlands Hiking Trail (PA DCNR): closures, drawn from pasda/warnings.py's ParkAdvisory resource
(decision 53, phase B, 2026-10-03).

The park's alerts page has one machine-readable channel, PA DCNR's ParkAdvisory API (park id 6219),
and pasda/warnings.py lands it once as `pa_dcnr_park_advisories`. A closure posted there would
arrive in that table, but as a warning: an advisory carries an IsAlert flag and HTML text, and no
structured status saying closed, so `obstructs_trail` stays false on it (decision 53, "Omit rather
than guess"). On 2026-10-03 none of the four items was a closure.

The page-banner fragment on pa.gov (`laurel-ridge-state-park-alert-cf`) is a standing pointer to
the alerts page, "Important Park Alerts & Advisories" since 2024-10-23, not a notice, so it is not
read. The trail's own conditions are posted on Facebook, which is not a notice source here.

ArcGIS layers read and not wired as closures or warnings (decision 53 phase B, 2026-10-03):
https://gis.dcnr.pa.gov/dcnrbsc/rest/services/Forestry, a folder listing, not a layer; not followed
(state forests are not the LHHT's manager).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "`services.dcnr.pa.gov/ParkAddresses/api/ParkAdvisory/get?id=6219` (the decision 53 inventory, batch 1,"
        " 2026-10-03): 4 items, each only {IsAlert, Message}; none closes the trail. Found in the alerts page's "
        "`data-api-url` and `data-park-id`, which is why that page's Danger and Information sections read empty "
        "to the coverage audit (2026-10-01).",
        "(the inventory, 2026-10-03) The park-page banner through pa.gov's AEM persisted query "
        "`get-alert-by-path;alertPath=…/laurel-ridge-state-park-alert-cf`: alertType 'warning', title "
        "'Important Park Alerts & Advisories', startDateAndTime 2024-10-23, endDateAndTime null, a link to the "
        "alerts page and nothing else.",
    ),
    where=(
        "https://services.dcnr.pa.gov/ParkAddresses/api/ParkAdvisory/get?id=6219",
        "https://www.pa.gov/agencies/dcnr/recreation/where-to-go/state-parks/find-a-park/laurel-ridge-state-park/alerts",
        "https://www.pa.gov/graphql/execute.json/copapwp/get-alert-by-path;alertPath=/content/dam/copapwp-pagov/en/dcnr/content-fragments/state-parks-forests-alerts/laurel-ridge-state-park-alert-cf",
    ),
    reason="drawn from pasda/'s resources, extracted once there (decision 34); checked names the layer this org's data"
    " arrives in",
)
