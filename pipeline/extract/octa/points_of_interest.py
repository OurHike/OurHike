"""Oregon-California Trails Association: points of interest, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

The High Potential Sites layers carry `Threats_to_Resources_Visitor_Services` and
`Current_Status_Action_Needed_for_Preservation`. That looks like preservation working data, and
publishing fragile rut locations could harm them. Ask OCTA before treating it as public POIs

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Own: `Hastings_Cutoff_WFL1`: Carsonite markers 343, rail post markers 89, signage 21, features 308, "
        "class 1–5 points 217. `High_Potential_Sites`: 10 state layers, about 296 points (CA 54, OR 41, NV 40, "
        "WY 39, ID 38, NE 27, UT 25, KS 22, MO 8, WA 2), edited 2026-09-29. Upstream: NTIR POIs, `oreg` 226, "
        "`cali` 371",
    ),
    where=(
        "https://mapservices.nps.gov/arcgis/rest/services",
        "https://octa-trails.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
