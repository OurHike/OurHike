"""The Trustees of Reservations: warnings, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

A PDF plus pages. Its names join to the `Trustees_props` polygons (places row). Why the original
missed it: the site's `place`, `content` and `program` post types are not registered in the WP REST
API (`/wp-json/wp/v2/types` lists only post/page/attachment and core types), so `/wp/v2/search`
cannot …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://thetrustees.org/content/hunting-on-trustees-properties/` (modified 2026-09-16) explains that "
        '"Roughly half of our properties allow some form of hunting", in three designations. It links '
        "`https://thetrustees.org/wp-content/uploads/2025/10/TrusteesPropertyHuntingDesignations_Oct2025.pdf` "
        "(PDF, 48,295 B, last-modified 2026-02-20), the per-property list. Each place page's \"Regulations & "
        'Advisories" states its own rule, e.g. Notchview: "Hunting is permitted at this property north of Bates'
        " Rd and south of Route 9 only… wear brightly colored clothing like an orange vest or hat during the …",
    ),
    where=(
        "https://thetrustees.org/content/hunting-on-trustees-properties/",
        "https://thetrustees.org/wp-content/uploads/2025/10/TrusteesPropertyHuntingDesignations_Oct2025.pdf",
        "https://thetrustees.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
