"""What an artifact is served as, by extension - the content-type tables.

Extracted from publish.py (#845), and the reason is the one lib/completeness
.py already records for `DROP_THRESHOLD`: two very different readers need
these, and only one of them can afford publish.py's dependencies.

`publish.py` imports boto3 at module scope, because uploading is its whole
job. `smoke_published.py` needs `COMPRESSIBLE_TYPES` to know which artifacts
are stored gzipped, and `verify_release.py` imports `smoke_published` - and
verify_release is the release gate, which by design runs with three
pure-Python packages installed (`requests pyyaml pmtiles`, per
.github/workflows/verify-release.yml) because it reads a bucket over plain
HTTP and holds no credentials.

So a single `from publish import COMPRESSIBLE_TYPES` put boto3 on the gate's
import path and stopped it starting at all. That had happened once before,
for the same reason with a different constant, and verify_release.py's own
docstring records it: "Importing the heavy module for one float made the
release gate unable to start at all (#514)." This module is that fix applied
to the second constant, so the third time cannot happen by this route.

Pure by construction: this file imports nothing. Keep it that way - the
value here is not where the tables live but what they let a reader avoid
importing.

The two tables are a pair and stay together. BINARY_TYPES is defined as
"everything else" relative to COMPRESSIBLE_TYPES, and splitting them would
leave that relationship asserted in one file about a table in another.
"""

from __future__ import annotations

# What an artifact is served as, by extension.
#
# UNTIL #717 THIS WAS NOTHING AT ALL. `upload_file` was called with no
# ExtraArgs, so every object landed in R2 with no Content-Encoding, no
# Cache-Control, and - for `.geojson`, which Python's mimetypes does not know -
# no Content-Type either. R2 does not compress on the fly, so what the bucket
# served was what a hiker downloaded, byte for byte.
#
# Measured against the live bucket 2026-08-15, requesting with
# `Accept-Encoding: gzip, br`, over the eleven artifacts the client fetches on
# every first launch:
#
#     served    21.5 MB   (22,542,491 bytes)
#     gzip -6    5.3 MB   ( 5,554,379 bytes)   4.1x
#
# trails.geojson alone is 12,308,084 -> 4,142,846, and elevation_profile.json
# 6,996,308 -> 914,415. The client's own comments have quoted the gzipped
# figures for years (client/src/lib/config.ts on elevation_profile.json: "6.5
# MB of JSON that gzips to 0.87 MB"); nothing was gzipping them.
#
# ONLY TEXT. The .pmtiles archives and .fgb files are read by BYTE RANGE -
# client/src/map/pmtilesSource.ts seeks within the archive, and
# client/src/lib/archiveDownload.ts resumes a partial transfer with a Range
# header. A stored Content-Encoding makes ranges refer to compressed offsets
# and breaks both, so those two extensions are deliberately absent from this
# table. They are also already compressed internally, so there is nothing to
# win and a download to lose.
#
# The published SHA-256 does not move. `latest.json` records the hash of the
# file on disk, and a client's `fetch` decodes Content-Encoding before any of
# its code sees the bytes - so client/src/lib/trailData.ts hashes exactly what
# was hashed here.
COMPRESSIBLE_TYPES = {
    ".json": "application/json",
    ".geojson": "application/geo+json",
}

# Everything else, named rather than guessed, so a new extension is a decision
# instead of an empty Content-Type.
BINARY_TYPES = {
    ".pmtiles": "application/vnd.pmtiles",
    ".fgb": "application/vnd.flatgeobuf",
}
