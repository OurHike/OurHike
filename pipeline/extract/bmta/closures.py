"""Benton MacKaye Trail Association: closures, published, and not landed (coverage audit 2026-10-01,
batch c8_regional_5).

PDF. Also `bmtamail.org/docs/KnowBeforeYouGo.pdf`.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '"Current Alerts & Advisories", `https://bmtamail.org/docs/CurrentAlertsandAdvisories.pdf`: a 1-page '
        "PDF, Last-Modified 2026-09-09, 289,535 B. It held 0 closure items today, but it is the channel the "
        "BMTA posts to.",
    ),
    where=(
        "https://bmtamail.org/docs/CurrentAlertsandAdvisories.pdf",
        "https://bmtamail.org/docs/KnowBeforeYouGo.pdf",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
