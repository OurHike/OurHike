"""Mohonk Preserve: closures, published, and not landed (coverage audit 2026-10-01, batch
b4_oprhp_mohonk_gatc).

The alerts page has a real change signal (`modified`), as ALERTS_NOTICES_SURVEY.md §6 found. The
peregrine closures are cliff areas with no published geometry. They would be `place_text` only.
Skeptic additions (Measured 2026-10-01): the page still reads "There are currently not closures" …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Other sources still to wire (decision 53 phase B, 2026-10-03; the phase A inventory has each one's
robots.txt, terms and change check): https://mohonkpreserve.org/wp-json/wp/v2/pages/13789
(wordpress); https://mohonkpreserve.org/wp-json/wp/v2/pages?slug=peregrine-watch-updates
(wordpress); https://mohonkpreserve.org/wp-json/wp/v2/wphash_ntf_bar (wordpress).
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`wp-json/wp/v2/pages/13789` (`/visit/alerts/`), `modified` 2026-09-28. It has a "Closures" section, '
        'which today reads "There are currently not closures". '
        "`/what-we-do/conservation-programs/conservation-science/peregrine-watch-updates/` (`modified` "
        '2026-05-12) posts dated temporary climbing and bouldering closures, e.g. "4.2.26 … a reduced, '
        'temporary closure will be in place starting Friday, April 3rd" and adjusted boundaries "effective '
        'Wednesday, April 15th".',
    ),
    where=("https://mohonkpreserve.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
