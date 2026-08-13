"""Fetch the PDFs the maintaining clubs publish, as sources.json registers
them (#669, `kind: "club_pdf"`) - GATC's water-sources list first.

SOURCE_SURVEY.md §5 walked all thirty clubs and found their data is
overwhelmingly PDFs and hand-maintained HTML, some of it carrying facts no
GIS layer publishes - GATC's PDF is mile-by-mile water for the whole state,
reliability notes included ("Typically very low or dry. Use creek at MP 2.9").
This script is the registry-driven fetch step, so the next club document is
one sources.json entry and (optionally) one parser in lib/club_pdfs.py, not a
new script.

What it does per registered entry, change-aware like every fetcher here:

  1. Conditional GET against the entry's `url` - If-None-Match /
     If-Modified-Since from this script's own manifest. A 304 (or an
     unchanged body hash - WordPress does not always honour conditionals)
     skips the work.
  2. Saves the PDF to data/raw/club_pdfs/<key>.pdf.
  3. Where lib/club_pdfs.py registers a parser for the key, extracts the text
     (pypdf) and writes the parsed rows to <key>.json beside the PDF. A key
     with no parser still fetches - the PDF and its hash land in the
     manifest, which is what "fetched for review" means - and says so.
  4. Records everything in data/raw/club_pdfs/manifest.json, and a fetch
     receipt (lib/fetch_receipts) so packaging can tell a completed run from
     one that never happened (#542).

A parse failure keeps the previous PDF, rows and manifest entry exactly as
they were and exits non-zero - the strict-header posture of
build_shelter_capacity.py, applied to a fetch: a PDF whose layout changed
must stop here, where a human reads the error, rather than land half-parsed.

## Licence: fetching-for-review is the whole scope

Club PDFs carry no stated terms (SOURCE_SURVEY.md §9's whole club row), so
nothing this script writes may reach a published artifact - no export reads
data/raw/club_pdfs/, and that is enforced by absence rather than by a flag:
wiring a club document into an export is a separate change that starts with
the club answering the ask its registry entry records. WATER_SOURCES.md §4
sizes GATC's PDF as exactly that - "a pilot-state candidate after an email" -
and CONTRIBUTING.md's "A note on data and licences" is the standing rule.
"""

import hashlib
import io
import json
import sys
from pathlib import Path

import requests

from lib.club_pdfs import PARSERS
from lib.fetch_receipts import record
from lib.source_registry import club_pdf_sources, load_registry

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / "sources.json"
OUT_DIR = ROOT / "data" / "raw" / "club_pdfs"
MANIFEST_PATH = OUT_DIR / "manifest.json"

USER_AGENT = "OurHike-pipeline/1.0 (+https://github.com/OurHike/OurHike)"
TIMEOUT = 120

FETCHER_NAME = "fetch_club_pdfs"


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def conditional_headers(state: dict, pdf_path: Path) -> dict:
    """The If-None-Match / If-Modified-Since pair for one entry - but only
    while the PDF the state describes is still on disk. State without the
    file would turn a deleted download into a permanent 304."""
    if not pdf_path.exists():
        return {}
    headers = {}
    if state.get("etag"):
        headers["If-None-Match"] = state["etag"]
    if state.get("last_modified"):
        headers["If-Modified-Since"] = state["last_modified"]
    return headers


def extract_page_texts(pdf_bytes: bytes) -> list[str]:
    """One plain-extraction string per page, in page order - the shape every
    parser in lib/club_pdfs.py takes. Plain rather than layout mode because
    the one document measured stores each row as a single fragment either
    way (lib/club_pdfs.py's docstring holds the measurement).

    pypdf is imported here rather than at module top, and is deliberately
    not in requirements.in's pins - it is an ad-hoc install exactly like
    tifffile's corrupted-quad check, and requirements.in records why. The
    error a bare environment gets says what to do, not just what is missing.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SystemExit(
            "fetch_club_pdfs.py needs pypdf to read the PDFs - `pip install pypdf`. "
            "It is an ad-hoc install on purpose; pipeline/requirements.in explains."
        ) from exc
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return [page.extract_text() or "" for page in reader.pages]


def fetch_entry(entry: dict, state: dict) -> tuple[dict, bool]:
    """Fetch one registered PDF; returns (new manifest state, changed).

    Raises on HTTP failure and on parse failure, writing nothing in either
    case - the caller decides whether other entries still run (they do; one
    club's broken PDF must not block another's fetch).
    """
    key = entry["key"]
    pdf_path = OUT_DIR / f"{key}.pdf"

    response = requests.get(
        entry["url"],
        headers={"User-Agent": USER_AGENT, **conditional_headers(state, pdf_path)},
        timeout=TIMEOUT,
    )
    if response.status_code == 304:
        print(f"  {key}: up to date (304 Not Modified).")
        return state, False
    response.raise_for_status()

    body = response.content
    digest = hashlib.sha256(body).hexdigest()
    if state.get("sha256") == digest and pdf_path.exists():
        # Same bytes re-served without a 304 - WordPress installs do that.
        # Refresh the validators so the next run's conditional has the best
        # chance of a real 304, but do not re-parse what did not change.
        print(f"  {key}: unchanged (same sha256, {len(body):,} bytes).")
        refreshed = dict(state)
        refreshed["etag"] = response.headers.get("ETag") or state.get("etag")
        refreshed["last_modified"] = response.headers.get("Last-Modified") or state.get("last_modified")
        return refreshed, True

    parser = PARSERS.get(key)
    rows = None
    if parser is not None:
        # Parse BEFORE persisting anything: a PDF whose layout changed must
        # leave the previous known-good PDF and rows in place (docstring).
        rows = parser(extract_page_texts(body))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(body)
    written = [pdf_path]

    if rows is not None:
        rows_path = OUT_DIR / f"{key}.json"
        rows_path.write_text(
            json.dumps(
                {
                    "source": key,
                    "url": entry["url"],
                    "provider": entry.get("provider"),
                    "licence_note": (
                        "Fetched for review and cross-checks only - the registry entry's `licence` "
                        "records why nothing here reaches a published artifact yet."
                    ),
                    "rows": rows,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        written.append(rows_path)
        print(f"  {key}: {len(body):,} bytes, parsed {len(rows)} rows -> {rows_path.name}")
    else:
        print(f"  {key}: {len(body):,} bytes saved; no parser registered in lib/club_pdfs.py yet - PDF kept for review.")

    return {
        "url": entry["url"],
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
        "sha256": digest,
        "bytes": len(body),
        "rows": len(rows) if rows is not None else None,
        # Names, not paths: the manifest lives beside these files, so a name
        # is unambiguous and survives the whole directory being relocated -
        # which is exactly what every test here does to it.
        "files": [path.name for path in written],
    }, True


def main() -> int:
    registry = load_registry(SOURCES_PATH)
    entries = club_pdf_sources(registry)
    if not entries:
        print("No club_pdf sources registered in sources.json - nothing to fetch.")
        return 0

    manifest = load_manifest()
    failures = []
    changed = False
    for entry in entries:
        key = entry["key"]
        print(f"Fetching {key} from {entry['url']} ...")
        try:
            manifest[key], entry_changed = fetch_entry(entry, manifest.get(key, {}))
            changed = changed or entry_changed
        except Exception as exc:  # noqa: BLE001 - each entry reports, the run fails at the end
            failures.append(f"{key}: {exc}")
            print(f"  {key}: FAILED - {exc}")

    if changed:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"Manifest -> {MANIFEST_PATH}")

    if failures:
        # Like fetch_all.py: a failed source fails the run, out loud, so a
        # rotted club URL is a red build and not a quietly ageing PDF.
        print(f"{len(failures)} club PDF fetch(es) failed:")
        for failure in failures:
            print(f"  {failure}")
        return 1

    # The receipt covers the files every successful entry stands behind -
    # including runs that were all 304s, which are this fetcher succeeding
    # (the same reasoning as fetch_opentrail.py's skip-path receipt).
    receipt_files = [OUT_DIR / name for state in manifest.values() for name in state.get("files", [])]
    record(FETCHER_NAME, [path for path in receipt_files if path.exists()])
    return 0


if __name__ == "__main__":
    sys.exit(main())
