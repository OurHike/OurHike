"""The human half of the face gate (#836): look at what the screen flagged,
then record what you concluded.

Run bare, it writes an HTML review page to data/review/photo_screen.html -
every Commons photo the screen flagged that nobody has decided on yet, the
photograph itself first (the whole judgement is made by looking), with its
waypoint, its Commons provenance, and the exact command that records each
verdict. Then:

    python review_flagged_photos.py --clear <digest>  [--note "..."]
    python review_flagged_photos.py --refuse <digest> [--note "..."]

writes the decision into reference/photo_screen_decisions.json, which is
committed - the diff of that file is the review of the judgement, so a note
saying what you saw ("trail crew group shot", "empty shelter, flag was a
knot in the siding") is worth the keystrokes. A cleared photo ships on the
next export; a refused one stays out permanently; identical bytes never
re-ask either way (decisions key on the content digest).

The page embeds each image as a data URI from the local cache rather than
linking anything: it must work offline, and a review page that hotlinks
upload.wikimedia.org would spend the nonprofit's bandwidth on exactly the
traffic #362 moved off it. A held photo whose bytes are not cached locally
says so on the page instead of showing a broken image.

Output lives in data/review/ - generated, gitignored, rebuilt on demand -
never in the repository (CONTRIBUTING.md "Data does not go in commits").
"""

import base64
import json
import sys
from pathlib import Path

from lib.photo_screen import DECISIONS_PATH, flagged, load_decisions, record_decision
from lib.photo_store import local_photo_path

RAW_DIR = Path(__file__).parent / "data" / "raw"
OUTCOMES = ("poi_images.json",)
OUT_PATH = Path(__file__).parent / "data" / "review" / "photo_screen.html"


def held_photos(raw_dir: Path, decisions: dict[str, dict]) -> list[dict]:
    """Every flagged, undecided photo across the outcome files, oldest
    check first, each row carrying what the page needs: the digest (the
    photo's name in every command), the POI it would illustrate, what the
    screen found, and the Commons provenance a reviewer may want to open."""
    rows = []
    for filename in OUTCOMES:
        path = raw_dir / filename
        if not path.exists():
            continue
        outcomes = json.loads(path.read_text(encoding="utf-8")).get("pois", {})
        for poi_id, record in sorted(outcomes.items()):
            if record.get("status") != "found":
                continue
            photos = record["photos"] if "photos" in record else ([record["photo"]] if "photo" in record else [])
            for photo in photos:
                digest = photo.get("digest")
                if not digest or not flagged(photo) or digest in decisions:
                    continue
                rows.append(
                    {
                        "digest": digest,
                        "poi_id": poi_id,
                        "faces": photo["screen"]["faces"],
                        "screened_on": photo["screen"].get("on", ""),
                        "page_url": photo.get("page_url", ""),
                        "author": photo.get("author"),
                        "license": photo.get("license", ""),
                        "taken": photo.get("taken", ""),
                    }
                )
    return rows


def embedded_image(raw_dir: Path, digest: str) -> str | None:
    """The cached bytes as a data URI, or None when they are not on disk
    (a digest-only carry-forward, #465 - the record can be published but
    this page cannot show it)."""
    path = local_photo_path(raw_dir, digest)
    if not path.exists():
        return None
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def render_page(rows: list[dict], raw_dir: Path) -> str:
    """One self-contained HTML page. Deliberately artless: this is a work
    surface for one person, not a product screen."""
    parts = [
        "<!doctype html><meta charset='utf-8'><title>Flagged photos awaiting a look</title>",
        "<style>body{font:16px/1.5 sans-serif;max-width:44em;margin:2em auto;padding:0 1em}"
        "img{max-width:100%;border:1px solid #999}article{margin:0 0 3em}code{background:#eee;padding:0 .3em}</style>",
        f"<h1>{len(rows)} flagged photo(s) awaiting a look</h1>",
        "<p>The screen only sorts; you decide. A cleared photo ships on the next export, a"
        " refused one stays out permanently. Record each verdict with the command under its photo.</p>",
    ]
    if not rows:
        parts.append("<p>Nothing is waiting. Every flagged photo has a recorded decision.</p>")
    for row in rows:
        image = embedded_image(raw_dir, row["digest"])
        img_html = (
            f"<img src='{image}' alt=''>"
            if image
            else "<p><strong>Bytes not cached locally</strong> - run the fetch (or --recheck) before judging this one; the digest below still names it.</p>"
        )
        author = row["author"] or "no author recorded"
        parts.append(
            f"<article>{img_html}"
            f"<p><strong>{row['poi_id']}</strong> - screen found {row['faces']} face(s) on {row['screened_on']}.<br>"
            f"{author}, {row['license']}, taken {row['taken']} - <a href='{row['page_url']}'>Commons page</a></p>"
            f"<p><code>python review_flagged_photos.py --clear {row['digest']}</code><br>"
            f"<code>python review_flagged_photos.py --refuse {row['digest']}</code></p>"
            "</article>"
        )
    return "".join(parts)


def build_page() -> None:
    # DECISIONS_PATH passed explicitly rather than left to the default, so
    # everything in this script reads and writes one ledger - the module
    # global tests can repoint.
    decisions = load_decisions(DECISIONS_PATH)
    rows = held_photos(RAW_DIR, decisions)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(render_page(rows, RAW_DIR), encoding="utf-8")
    print(f"{len(rows)} flagged photo(s) awaiting a look -> {OUT_PATH}")


def decide(decision: str, digest: str, note: str | None) -> None:
    record_decision(digest, decision, note=note, path=DECISIONS_PATH)
    # A decision for a digest no current outcome file mentions is recorded
    # anyway - the ledger outlives any one crawl - but it is worth a word,
    # because the likeliest cause is a pasted-wrong digest.
    if not any(row["digest"] == digest for row in held_photos(RAW_DIR, {})):
        print(f"Recorded, but no flagged photo in the current outcome files has digest {digest} - check for a paste slip.")
    else:
        print(f"Recorded: {digest} {decision} -> {DECISIONS_PATH}")
    if decision == "refused":
        # publish.py stops uploading it from here on, but cannot recall an
        # object a previous run already published.
        print(
            f"If a previous publish already uploaded it, delete photos/{digest}.jpg from the bucket by hand - refusing only stops future uploads."
        )


def run(argv: list[str]) -> None:
    """Bare run builds the page; --clear/--refuse record a decision. An
    unknown flag is rejected rather than ignored, same as every fetch
    script - a typo must not quietly build the page instead of recording
    the verdict you thought you recorded."""
    if not argv:
        build_page()
        return
    flag = argv[0]
    if flag not in ("--clear", "--refuse") or len(argv) < 2:
        print("usage: python review_flagged_photos.py [--clear|--refuse <digest> [--note '...']]")
        raise SystemExit(2)
    digest = argv[1]
    note = None
    rest = argv[2:]
    if rest and rest[0] == "--note" and len(rest) == 2:
        note = rest[1]
    elif rest:
        print("usage: python review_flagged_photos.py [--clear|--refuse <digest> [--note '...']]")
        raise SystemExit(2)
    decide("cleared" if flag == "--clear" else "refused", digest, note)


if __name__ == "__main__":
    run(sys.argv[1:])
