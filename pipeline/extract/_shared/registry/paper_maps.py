"""NYNJTC's paper maps, as a person joined them: reference/nynjtc_paper_maps.json, landed whole as
`raw_registry__nynjtc_paper_maps`.

12 products on 2026-10-01, each with the sheets it holds and the parks each
sheet covers, in NYNJTC's own spelling. sources.json's `nynjtc_store` block
names this file (`paper_maps`), and the steward's store record publishes it,
so it is the registry's input and lands beside sources.json. The store itself
is never read: its read was by hand (the file's `store.read_how`).

A store block naming a file no resource here lands fails the build in
int_sources__stewards rather than publishing a store with no maps.
"""

from extract._kinds import reviewed_file

TYPE = "org"
CLAIMS = ("reference/nynjtc_paper_maps.json",)
RESOURCES = [reviewed_file("reference/nynjtc_paper_maps.json", rows_key=None, verbatim=True)]
