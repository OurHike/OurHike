"""Bureau of Land Management: challenges, published, and not landed (coverage audit 2026-10-01, batch
b6_federal).

Page only. The stamp sites would need geocoding.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://www.blm.gov/programs/recreation/recreation-activities/new-mexico/commemorative-anniversary-stamps`:"
        ' "Passport Stamps now available for New Mexico and West Texas National Historic Trails", with a "Where'
        ' Can I get my passport stamps?" section. Iditarod NHT passport (c11).',
    ),
    where=("https://www.blm.gov/programs/recreation/recreation-activities/new-mexico/commemorative-anniversary-stamps",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
