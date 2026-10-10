"""Names read back from a private store, checked before one becomes a SQL identifier or a local path.

THE NAMES COME FROM FILES ANYBODY HOLDING THE STORE'S KEY CAN WRITE. The
build reads table names and file paths back from the stores it shares a key
with: the raw store's run log (`_extract_runs`), a pin's `raw_inputs.json`, a
served copy's `manifest.json` and a load's as-landed `index.json`
(extract/_warehouse.py), and the row-history store's `history.json` and
`elementary.json` (row_history.py). A run of this repository wrote each of
them, and so could anyone else with the key. Before this module those names
went into SQL and local paths as they were read, so a crafted name could run
SQL in a build job or write a file outside the directory it was meant for
(review finding of PR #1805 — dlt → dbt re-platform as one go/no-go change).
Measured 2026-10-09 on duckdb 1.5.5, the version every requirements file
pins: load_pinned()'s own f-string, given a pin whose table name was
`x" AS SELECT 1 AS a; COPY (SELECT 'smuggled' AS b) TO '<path>'; --`, wrote
that file; and a `history.json` naming its table `../<…>/escaped` made
row_history.py's restore write `escaped.parquet` outside its temporary
directory and report the restore as a success.

So every such name passes one of three things here before it is used:

- table_name(): `[a-z0-9_]+` and nothing else. Every raw table is
  `raw_<folder>__<key>` (extract/_contract.py's raw_table()), and on
  2026-10-09 all 757 tables of discover()'s 901 resources and all 730
  sources.json keys matched it (Measured against this tree), as do dlt's own
  `_dlt_*` tables, the run log's `_extract_*` tables and every dbt snapshot
  (`int_<mart>__history`). A name that fails it was not written by this
  repository.
- relative_path(): extract/_warehouse.py's step-cache rule, moved here so both
  files share it: not empty, not absolute, no `..` segment. Enough that a path
  joined onto a directory or a store prefix stays under it. lib/raw_keys.py's
  stricter rule, which also refuses any character outside A-Z a-z 0-9 . _ -,
  is not applied here: nobody has checked that every path a stored pin or
  index already holds meets it, and a legal path refused would stop a build
  for nothing (Reasoned).
- quote_identifier(): row_history.py's `_quote()`, moved here: the name in
  double quotes, each double quote inside it doubled, as SQL quotes an
  identifier. Used on every name a statement is built from, after the check
  above, so a name that slipped past a check still could not end its quotes.
"""

from __future__ import annotations

import re

#: A table name read back from a store: lower-case letters, digits and underscores (the module docstring).
TABLE_NAME = re.compile(r"[a-z0-9_]+")


class StoreNameRefused(ValueError):
    """A name read back from a store that is not one this repository writes."""


def table_name(name: object, where: str) -> str:
    """`name`, or StoreNameRefused saying `where` it was read, when it is not `[a-z0-9_]+`."""
    if not isinstance(name, str) or not TABLE_NAME.fullmatch(name):
        raise StoreNameRefused(
            f"{where} names a table {name!r}, which is not lower-case letters, digits and underscores; no run of this "
            "repository writes such a name, so it is refused rather than read into SQL or a path"
        )
    return name


def relative_path(path: object, where: str) -> str:
    """`path`, or StoreNameRefused saying `where` it was read, when it is empty, absolute or has a `..` segment."""
    if not isinstance(path, str) or not path or path.startswith("/") or ".." in path.split("/"):
        raise StoreNameRefused(
            f"{where} names a path {path!r}, which is empty, absolute or climbs out with `..`; it is refused rather "
            "than joined onto a directory it could leave"
        )
    return path


def quote_identifier(name: str) -> str:
    """`name` as a quoted SQL identifier: in double quotes, each double quote inside it doubled."""
    return '"' + name.replace('"', '""') + '"'
