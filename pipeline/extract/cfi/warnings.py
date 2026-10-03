"""Colorado Fourteeners Initiative: warnings, published, and not landed (coverage audit 2026-10-01,
batch c5_regional_2).

These are static hazards, written 2012–2017. The mine-stope hazard is the kind that stays true.
(Skeptic: the Bross page's stope text was confirmed. `/mountain-safety/` (sitemap lastmod
2019-10-23) is three video series: Mountain Safety, Intro to 14er Gear, Understanding Altitude
Illness. That is …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Each peak page has "Peak Specific Environmental and Safety Concerns": lightning above treeline, and on'
        ' Lincoln, Democrat and Bross, collapsing mine stopes "only inches from the surface".',
    ),
    where=("https://14ers.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
