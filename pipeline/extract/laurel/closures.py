"""Laurel Highlands Hiking Trail (PA DCNR): closures, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

The JSON channel exists. Whether per-closure items flow through it is not confirmed (Unvalidated).
The trail's own conditions live on Facebook (see terms). Skeptic spot check: the Laurel Ridge
fragment answers with `alertType: "warning"`, title "Important Park Alerts & Advisories" …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.pa.gov/agencies/dcnr/recreation/where-to-go/state-parks/find-a-park/laurel-ridge-state-park/alerts`"
        ' has "Danger" and "Information" sections. Both were empty when read 2026-10-01, possibly because they '
        "render by script. The park-page banner is JSON through pa.gov's AEM persisted query: "
        "`https://www.pa.gov/graphql/execute.json/copapwp/get-alert-by-path; "
        "alertPath=/content/dam/copapwp-pagov/en/dcnr/content-fragments/state-parks-forests-alerts/laurel-ridge-state-park-alert-cf`"
        " (`alertType`, `startDateAndTime`, `endDateAndTime`).",
    ),
    where=(
        "https://www.pa.gov/agencies/dcnr/recreation/where-to-go/state-parks/find-a-park/laurel-ridge-state-park/alerts",
        "https://www.pa.gov/graphql/execute.json/copapwp/get-alert-by-path",
        "https://pa.gov",
        "https://dcnr.pa.gov/",
        "https://www.pa.gov/graphql/execute.json/copapwp/get-alert-by-path;alertPath=/content/dam/copapwp-pagov/en/dcnr/content-fragments/state-parks-forests-alerts/laurel-ridge-state-park-alert-cf",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
