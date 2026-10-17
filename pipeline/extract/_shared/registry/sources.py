"""The source registry itself: sources.json, reviewed in git, landed whole as `raw_registry__sources`.

64 registered sources on 2026-10-01, and beside them the blocks that are
facts about an organization rather than about one layer: each steward's
`<x>_licence` terms, `<x>_support` donate line and `<x>_store` paper-map shop,
the `organizations` ids and the `org_marks` asks. export_sources.py joins the
two into stewards.json and registry.json, and the sources mart does now.

One row, the whole document as written (ReviewedFile's `verbatim`), because
the blocks are top-level keys with no list to be rows of, and because a block
is matched to its steward by its `author` among keys in file order: the first
block that names a steward is the one it gets (export_sources.py's `_block`).
"""

from extract._kinds import reviewed_file

TYPE = "org"
CLAIMS = ("sources.json",)
RESOURCES = [reviewed_file("sources.json", rows_key=None, verbatim=True)]
