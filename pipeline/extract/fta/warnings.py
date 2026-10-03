"""Florida Trail Association: warnings, read with closures (decision 53 phase B, 2026-10-03).
closures.py's notice sources feed this type too: one upstream is one resource and one raw table
(decision 34), and dbt's decision 7 classifier splits each notice into closures or warnings.

Before decision 53 phase B, 2026-10-03, this file was a note. It read, whole:

Florida Trail Association: warnings, published, and not landed (coverage audit 2026-10-01, batch
c10_nst_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): NTH posts in the same categories: "Free Bear Canisters
Available… Ocala National Forest", "National Forest Bear Policy", "Camping Prohibited at Camp
Blanding". Page `https://floridatrail.org/hiker-safety/`: static guidance on hunting season (links
FWC season dates), named flood-prone rivers, and personal safety.

Its `where`: https://floridatrail.org/hiker-safety/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a
registered key
"""

SHARES = "closures"
