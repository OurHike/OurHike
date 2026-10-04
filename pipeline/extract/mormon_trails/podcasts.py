"""Mormon Trails Association: podcasts, drawn from nps/podcasts.py's `nps_multimedia_audio` (decision
54 wave 3, section C, 2026-10-04).

NPS's audio list (`/multimedia/audio`) lands once, in nps/podcasts.py, read whole, nationally, so
park code `mopi` is in it, and dbt assigns this folder its portion by each row's own park list
matched to nps_alerts' `park_codes` map, the one home for which folder draws on which park (decision
34). It needs NPS_API_KEY; without it the table is withdrawn, never read as empty
(extract/_json_apis.py, 'THE KEY').

The note this replaces read, whole:

National Mormon Trails Association: podcasts, published, and not landed (coverage audit 2026-10-01,
batch c11_nht).

Own `/videos/` reads "COMING SOON"; YouTube `@thenmta`

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "NPS `/multimedia/audio` (section C, 2026-10-04): landed by nps/podcasts.py as nps_multimedia_audio, national; this folder's park code: mopi.",
        "(the coverage audit, 2026-10-01) `NPSAPI/multimedia/audio` mopi 10",
    ),
    where=(
        "https://developer.nps.gov/api/v1/multimedia/audio",
        "https://mormontrails.org/",
    ),
    reason="drawn from nps/'s resources, extracted once there (decision 34); checked names the dataset this org's data arrives in",
)
