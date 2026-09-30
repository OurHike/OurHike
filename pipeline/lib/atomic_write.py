"""Write a file so that a reader never sees half of it.

`Path.write_text` truncates the file first and then writes, so a process
killed between the two - a workflow step reaching its `timeout-minutes`,
which #1318 records happening twice to the ATC fetch, or a runner lost
mid-job - leaves a truncated file behind under the real name. For the hourly
caches in publish-conditions.yml that is not a lost hour: the save step is
`if: always() && hashFiles(...) != ''`, so the truncated file is exactly what
gets cached and restored into the next run, and `json.loads` on it fails
every hour after until somebody notices. The fetchers' docstrings promised
their caches were "written atomically at the end", and until this module
they were written once at the end, which is a different property.

The window is small: a `write_text` of a few hundred kilobytes takes well
under a millisecond, and the kill that matters arrives after minutes of
fetching, not during the write. Small is not zero, the fix is six lines, and
a docstring should not claim a property the code does not have.

Temporary file in the same directory (so the rename cannot cross a
filesystem), then `os.replace`, which POSIX guarantees is atomic: the path
names either the old bytes or the new ones, never a prefix of the new. On
any failure the temporary file is removed and the old file is untouched.

lib/fetch_receipts.py, lib/photo_screen.py, fetch_atc_photos.py,
fetch_poi_images.py and fetch_hikefinder.py each carry their own copy of the
same idiom, written before this one home existed; they are left as they are
rather than churned, and a new writer should use this.
"""

from __future__ import annotations

import os
from pathlib import Path


def write_text_atomically(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Replace `path`'s contents with `text` in one step, or leave `path` as it was."""
    path = Path(path)
    tmp_path = path.with_name(f"{path.name}.tmp")
    try:
        tmp_path.write_text(text, encoding=encoding)
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
