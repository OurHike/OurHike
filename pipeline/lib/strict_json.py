"""JSON read the way a phone reads it: `NaN` and `Infinity` are refused.

Python's `json` module is more generous than the standard it implements.
`json.dumps(float("nan"))` writes the bare token `NaN`, and `json.loads`
reads `NaN`, `Infinity` and `-Infinity` back without complaint. Neither is
JSON (RFC 8259 section 6 has no such tokens), and the reader that matters
here is not Python: it is `JSON.parse` in a WebView, which rejects the whole
document on the first one. Measured 2026-09-17 on Node 24 in this sandbox:
`[NaN]`, `[Infinity]` and `[-Infinity]` all throw. So one non-finite float
anywhere in an artifact is not one bad value; it is the entire artifact
unreadable on every phone that downloads it (#659 found exactly that in the
elevation profile, and export_elevation.py guards its own inputs since).

Where such a float can come from is not hypothetical. DuckDB 1.5.5 answers
`0.0/0.0` with `nan` and `1.0/0.0` with `inf` (measured here, the same
session), and the exporters project coordinates through pyproj, which hands
back `inf` for a point it cannot place. Nothing between an exporter and the
bucket parsed strictly until this module existed: check_output_quality.py,
verify_release.py, smoke_published.py and check_deployment.py all read with
`json.loads` or `response.json()`, so every gate would have passed a file the
phone rejects. Measured against production on 2026-09-17: none of the 236
JSON artifacts carried such a token. This is the gate for the day one does.

Two halves, deliberately small:

  loads / load    parse, and raise NonFiniteNumber on any of the three
                  tokens - the checkers' half.
  dumps           `json.dumps` with `allow_nan=False`, so an exporter that
                  adopts it fails at the write rather than publishing the
                  token - the writers' half. Adoption is per exporter; the
                  gate above is what covers the ones that have not.

Nothing else is changed about how JSON is read or written: indentation,
separators and key order are the caller's, exactly as with the stdlib.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TOKENS = ("NaN", "Infinity", "-Infinity")


class NonFiniteNumber(ValueError):
    """A `NaN`, `Infinity` or `-Infinity` token where a JSON reader on a phone
    would stop reading."""


def _refuse(token: str) -> Any:
    raise NonFiniteNumber(
        f"{token} is not JSON: Python writes and reads it, JSON.parse on a phone rejects the whole document on it"
    )


def loads(text: str | bytes | bytearray) -> Any:
    """`json.loads`, refusing the three tokens a phone cannot parse."""
    return json.loads(text, parse_constant=_refuse)


def load(path: Path) -> Any:
    """`loads` over a file's bytes."""
    return loads(Path(path).read_bytes())


def dumps(value: Any, **kwargs: Any) -> str:
    """`json.dumps` that raises `ValueError` on a non-finite float instead of
    writing a token no phone can read. Every other keyword is passed through."""
    kwargs.setdefault("allow_nan", False)
    return json.dumps(value, **kwargs)
