"""The Anza Trail Foundation: trail lines, published, and not landed (coverage audit 2026-10-01, batch
c11_nht).

The recreation trail is the one walkable NHT dataset in the NPS set. Owner `an email address`

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`NPSAGOL/JUBA_NHT_RECREATION_TRAILS/0`: 578 lines (2026-08-11; TRSURFACE Asphalt 144, Native Material "
        "173 …). `JUBA_NHT_` historic: 3. `JUBA_AutoTourRoute`: 1,084. `nps_trails`: 32 Anza rows in "
        'SAMO/GOGA/TUMA (LOADED fragments; a bare `%Anza%` match would claim 132 by catching "Manzanita"). '
        '`blm_trails`: 4 AZ "Anza Trail" rows (LOADED)',
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://anzatrailfoundation.com/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
