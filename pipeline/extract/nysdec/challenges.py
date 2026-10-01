"""The Catskills Fire Tower Challenge is a DEC web page and PDF, under DEC's Website Content Usage policy."""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "the 2026 Catskills Fire Tower Challenge page: 8 towers, a window of 2026-01-01 to 2026-12-31, a log PDF",
        "reference/challenges/publishers.json: DEC is not a publisher",
    ),
    where=("https://dec.ny.gov/things-to-do/hiking/catskills-fire-tower-challenge",),
    reason=(
        "a web page outside the clearinghouse decision; a challenge enters as a reviewed file under "
        "reference/challenges/, which needs DEC as a publisher first"
    ),
)
