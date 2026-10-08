"""Point /data/quality/ at the data this deploy serves (pipeline/ELT.md decision 102, step 4).

    DATA_URL=https://... python .github/scripts/configure_quality_page.py _site/data/quality/index.html

site/src/pages/data/quality/index.astro ships two placeholders, as data
attributes on the element its script reads, and this replaces them in the
assembled copy:

- `__DATA_BASE_URL__` with DATA_URL from the environment: the same base the
  app in this deploy is built with, so the page and the app cannot read two
  different buckets (the drift #457 was about, and the reason
  site/public/status/index.html takes its URL the same way). Through the
  environment, never pasted into a command, so the value is data and not
  code. An empty DATA_URL leaves the placeholder, and the page then says it is
  not configured, which is true and is a different sentence from "the checks
  failed"; this prints a warning saying so.
- `__DATA_RELEASE__` with client/src/lib/dataRelease.ts's DATA_RELEASE, read
  with the same pattern as pages.yml's "Confirm the pinned data release
  exists" step, so the monthly file the page reads is the one in the release
  this deploy's app pins.

Both are written into an HTML attribute, so both are HTML-escaped. Exit 1
when the page does not hold each placeholder exactly once or DATA_RELEASE
cannot be read: either means the page or the client moved, and this must be
updated rather than left substituting nothing.

One home for both callers: pages.yml's "Assemble the site" and
pr-preview.yml's "Assemble the preview" each run this on their own `_site`,
and .github/tests/test_data_quality_page.py holds both to it.
"""

from __future__ import annotations

import html
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RELEASE_FILE = REPO_ROOT / "client" / "src" / "lib" / "dataRelease.ts"
BASE_PLACEHOLDER = "__DATA_BASE_URL__"
RELEASE_PLACEHOLDER = "__DATA_RELEASE__"
#: The line pages.yml's pin check reads with `sed -n "s/^export const DATA_RELEASE = '\(.*\)'$/\1/p"`.
DATA_RELEASE_LINE = re.compile(r"^export const DATA_RELEASE = '(.*)'$", re.MULTILINE)
#: A release id, as client/src/lib/dataRelease.ts's RELEASE_ID spells one.
RELEASE_ID = re.compile(r"\d{4}-\d{2}-\d{2}(?:-\d+)?")


class Refused(Exception):
    """The page or the client is not shaped the way this step expects."""


def pinned_release(source: str) -> str:
    """DATA_RELEASE out of dataRelease.ts's source, or Refused."""
    match = DATA_RELEASE_LINE.search(source)
    if match is None or not RELEASE_ID.fullmatch(match.group(1)):
        raise Refused(
            "Could not read a release id out of client/src/lib/dataRelease.ts's DATA_RELEASE. It has been "
            "restructured, and this step must be updated rather than left pointing the page at nothing."
        )
    return match.group(1)


def configure(page: str, *, data_url: str, release: str) -> str:
    """The page with both placeholders replaced, the base left in place when `data_url` is empty."""
    for placeholder in (BASE_PLACEHOLDER, RELEASE_PLACEHOLDER):
        count = page.count(placeholder)
        if count != 1:
            raise Refused(
                f"The data-quality page holds {placeholder} {count} times, not once: it has been restructured, "
                "and this step must be updated with it."
            )
    page = page.replace(RELEASE_PLACEHOLDER, html.escape(release, quote=True))
    if data_url:
        page = page.replace(BASE_PLACEHOLDER, html.escape(data_url.rstrip("/"), quote=True))
    return page


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(argv[0])
    if not path.is_file():
        print(f"::error::{path} does not exist, so the data-quality page did not reach the site.", file=sys.stderr)
        return 1
    data_url = os.environ.get("DATA_URL", "").strip()
    try:
        release = pinned_release(DATA_RELEASE_FILE.read_text(encoding="utf-8"))
        path.write_text(configure(path.read_text(encoding="utf-8"), data_url=data_url, release=release), encoding="utf-8")
    except Refused as refused:
        print(f"::error::{refused}", file=sys.stderr)
        return 1
    if data_url:
        print(f"The data-quality page reads {data_url.rstrip('/')}, release {release}.")
    else:
        print("::warning::No DATA_URL, so /data/quality/ will say it is not configured rather than reading anything.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
