"""OurHike's reviewed trail-name aliases: reference/trail_name_aliases.json, landed whole as `raw_ourhike__trail_name_aliases`.

Which names each publisher uses for a through route, keyed by trail, with the
rejected candidates and the removed ones beside them; the network overview's
through routes read it (ledger row TL21). One row, the whole document as
written (ReviewedFile's `verbatim`), because `trails` is a map keyed by trail
id with no list to be rows of, and the `rejected` and `_removed` blocks are
part of what a reviewer reads.
"""

from extract._kinds import reviewed_file

TYPE = "trail_lines"
CLAIMS = ("reference/trail_name_aliases.json",)
RESOURCES = [reviewed_file("reference/trail_name_aliases.json", rows_key=None, verbatim=True)]
