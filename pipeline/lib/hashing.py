"""One sha256_file for the whole pipeline (#659: it was defined ten times).

Every manifest, receipt and publish decision in this repository rides on
"the SHA-256 of the file's bytes", and that rule had ten separate
definitions across the exporters, the publish step, the quality gate and
the fetch receipts - two of them a different implementation (whole-file
read) from the other eight (chunked). They all computed the same digest,
which is exactly why the duplication was invisible; the first divergence
would have been a manifest nothing could verify. One home, chunked, so a
1.6 GB raster archive hashes without holding 1.6 GB.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
