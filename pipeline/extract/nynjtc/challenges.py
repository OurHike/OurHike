"""New York–New Jersey Trail Conference: challenges, published, and not landed (coverage audit
2026-10-01, batch b2_nynjtc).

The challenge to load is the programme's definition: the 40 sections already in `nynjtc_long_path`
and `nynjtc_long_path_guide`, and the tally sheet's rules.; Never load the End-to-Enders roster. It
is a list of named private individuals with finish dates.; ~~The post does not say who runs the …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '• The Long Path End-to-End certification and "rocker" patch: `/navigating-the-long-path/` (modified '
        '2026-05-06), "the New York-New Jersey Trail Conference recognizes this with an official End-to-End '
        "certification … certificate and End-to-End 'rocker'\". The rules are on "
        "`/wp-content/uploads/2026/05/LP-End-2-End-Tally-Sheet_Apr2026-1.pdf`. The roster is "
        "`/wp-content/uploads/2026/05/LP-End-to-Enders_May-2026.pdf`. Formats: page/pdf.",
        "`/news/2019-long-path-end-to-enders/` numbers finishers (#165–#177 in 2019).",
        "`/news/earn-a-catskill-fire-towers-badge/` (2013, modified 2025-04-10) links …",
    ),
    where=("https://nynjtc.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
