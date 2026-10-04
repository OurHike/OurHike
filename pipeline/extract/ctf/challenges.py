"""Colorado Trail Foundation: challenges, refused by the host (decision 54 wave 5, section K, 2026-10-04).

coloradotrail.org answers HTTP 403 to our named agent (ctf/suggested_hikes.py); its completers' list ('2,698 known
completers') is a roster in any case, and its certificate and patch a completion award.

The note this replaces read, whole:

Colorado Trail Foundation: challenges, published, and not landed (coverage audit 2026-10-01, batch
c7_regional_4).

Pages.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `/completers-of-the-colorado-trail/` ("2,698 known completers",
per snippet), `/trail/completers/completer-certificate-request/` (a free digital certificate) and
`/product/completion-patch/`.

Its `where`: https://coloradotrail.org/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=("https://coloradotrail.org/: HTTP 403 to our agent, 2026-10-04 (ctf/suggested_hikes.py)",),
    where=("https://coloradotrail.org/",),
    reason="refused: the host answers HTTP 403 to our named agent",
)
