"""Continental Divide Trail Coalition: challenges, a completion award with no list of places, and not landed (decision
54 wave 5, section K, 2026-10-04).

/cdt-completers/: honour-system completion reporting with a certificate, a CDT patch and a '3000 Miler' rocker;
section hikers get equal recognition.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

Continental Divide Trail Coalition: challenges, published, and not landed (coverage audit 2026-10-01,
batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): Format page. `cdtcoalition.org/cdt-completers/`: honour-system
completion reporting with a certificate, a CDT patch and a "3000 Miler" rocker. Section hikers get equal
recognition.

Its `where`: https://cdtcoalition.org/cdt-completers/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) /cdt-completers/",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://cdtcoalition.org/cdt-completers/",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
