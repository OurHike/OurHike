"""NY-NJ Trail Conference: challenges, a completion award with no list of places, and not landed (decision 54 wave 5,
section K, 2026-10-04).

The Long Path End-to-End certification and its rocker patch: a hiker completes the whole Long Path and
submits a tally sheet (LP-End-2-End-Tally-Sheet_Apr2026-1.pdf); the End-to-Enders' list is a roster.

The challenges type holds a club's list of places on its trails (pipeline/ELT.md, decision 3, what #1780 — Let a
club publish a challenge — places on its own trails that hikers opt into and tag at camp — starting with the ATC's
A.T. Summer Bucket List builds), and a finisher's roster is never loaded (the round brief).

The note this replaces read, whole:

New York–New Jersey Trail Conference: challenges, published, and not landed (coverage audit 2026-10-01,
batch b2_nynjtc).

The challenge to load is the programme's definition: the 40 sections already in `nynjtc_long_path` and
`nynjtc_long_path_guide`, and the tally sheet's rules.; Never load the End-to-Enders roster. It is a
list of named private individuals with finish dates.; ~~The post does not say who runs the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): • The Long Path End-to-End certification and "rocker" patch:
`/navigating-the-long-path/` (modified 2026-05-06), "the New York-New Jersey Trail Conference recognizes
this with an official End-to-End certification … certificate and End-to-End 'rocker'". The rules are on
`/wp-content/uploads/2026/05/LP-End-2-End-Tally-Sheet_Apr2026-1.pdf`. The roster is
`/wp-content/uploads/2026/05/LP-End-to-Enders_May-2026.pdf`. Formats: page/pdf.
`/news/2019-long-path-end-to-enders/` numbers finishers (#165–#177 in 2019).
`/news/earn-a-catskill-fire-towers-badge/` (2013, modified 2025-04-10) links …

Its `where`: https://nynjtc.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "https://www.nynjtc.org/wp-content/uploads/2026/05/LP-End-2-End-Tally-Sheet_Apr2026-1.pdf (HTTP 200, 302,234 bytes, 2026-10-04): the tally sheet",
    ),
    where=("https://www.nynjtc.org/navigating-the-long-path/",),
    reason="not this type: a completion award, with no list of places (ELT.md decision 3); its roster is never read",
)
