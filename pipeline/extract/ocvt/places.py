"""Outdoor Club at Virginia Tech: places, drawn from another folder's resource (coverage audit
2026-10-01, batch p05_persist).

ATC: `maintainer_authorisation`. USFS: public domain. VA DCR: explicit_restriction, as for PATH.
Folders `atc/` and `usfs/`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Loaded: ATC `AT_Communities` has "Pearisburg" (Giles County, designated 2011-06-18) at the US 460 end '
        'and "Bland County" at the I-77 end. "Narrows" (designated Fall 2013) is the neighbouring Giles County '
        "town (Reasoned that it serves the same section). ATC parking under OCVT: 4 (audit). Not loaded: the "
        "GWJ boundary (EDW, 0808). Peters Mountain Wilderness (`EDW_Wilderness_02`, 4,520 acres) contains some "
        "of OCVT's own half-mile points (multipoint intersect, filtered to the OCVT polygon first). VA DCR "
        'Conservation Lands has 2 "Peters Mountain" records (NF Wilderness Area). Tried: 1 ocvt.club has …',
    ),
    where=(
        "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services",
        "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services",
        "https://outdoor.org.vt.edu/",
    ),
    reason="drawn from atc/'s resources, extracted once there (decision 34); checked names the layer this org's data arrives in",
)
