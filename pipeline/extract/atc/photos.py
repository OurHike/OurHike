"""ATC's facility photos arrive on the facility layers themselves, as the Photo1..Photo10 fields.

So the rows load with points_of_interest.py's resources, and this type shares
them. Reading each photo's capture date over a Range request stays
fetch_atc_photos.py's job until it is ported, because it reads bytes, and
bytes never enter DuckDB (ELT.md, decision 4).
"""

SHARES = "points_of_interest"
