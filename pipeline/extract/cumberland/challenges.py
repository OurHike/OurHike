"""Cumberland Trail / Tennessee State Parks: challenges, Tennessee State Parks' passport, and not landed (decision 54
wave 5, section K, 2026-10-04).

The TN State Parks Passport keeps stamp stations at park visitor centres, with a completion form and certificate;
the bucket list and the signature hikes are posts. A park-visit stamp passport is not a list of places on trails.

The note this replaces read, whole:

Cumberland Trail / Tennessee State Parks: challenges, published, and not landed (coverage audit
2026-10-01, batch c9_federal_state_rest).

Page. No CT-specific end-to-end program found.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): TN State Parks Passport,
`https://tnstateparks.com/inspiration/passport`: stamp stations at visitor centres, plus a completion
form and certificate ("Do I get a certificate of accomplishment? YES!"). Skeptic adds:
`https://tnstateparks.com/inspiration/end-of-summer-bucket-list` (HTTP 200, a bucket-list post) and the
four statewide "Signature Hikes" a year (First Day, Spring, National Trails Day, After-Thanksgiving; per
`tn.gov/environment/news/2026/3/12/tn-state-parks-spring-hikes.html`, from search). Signature Hikes are
events, not a completion programme. A 2026 "Tennessee State Parks …

Its `where`: https://tnstateparks.com/inspiration/passport
https://tnstateparks.com/inspiration/end-of-summer-bucket-list
https://tn.gov/environment/news/2026/3/12/tn-state-parks-spring-hikes.html

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "(the coverage audit, 2026-10-01) https://tnstateparks.com/inspiration/passport",
        "no request sent today: the coverage audit's reading, 2026-10-01",
    ),
    where=("https://tnstateparks.com/inspiration/passport",),
    reason="not this type: a stamp passport kept at visitor centres, not places on trails",
)
