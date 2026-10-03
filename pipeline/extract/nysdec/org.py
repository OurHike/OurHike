"""NYS DEC's catalogue row: reference/trail_orgs.json, slug `nysdec`.

The statewide Forest Ranger line, 833-NYS-RANGERS, is DEC's published number
for an emergency in the backcountry. It belongs in this row rather than in a
layer: Forest Ranger Contact's per-ranger names and phone numbers are person
fields and never load (ELT.md, "Who may publish", rule 8). Adding it to
trail_orgs.json is a reviewed change to that file, not made here.
"""

from extract._kinds import catalogue_row

RESOURCES = [catalogue_row()]
