"""The face check a fetched community photo passes through before export,
and the gate that holds a flagged one back until a person has looked (#836).

Wikimedia Commons is the one photo source in this pipeline where the
photographer is an anonymous stranger and the subject may be too: a
geosearch hit near a shelter is routinely somebody's trip snapshot with
somebody's friends in it. features/POI_PHOTOS.md's position is that a
waypoint card is a picture of a place, and putting a recognizable person on
one - republished onto every phone that downloads the corridor - should
happen only after a human has looked at the photo and decided it is fine.
This module is the machine half of that: it does not decide anything, it
only sorts which photos a person needs to look at.

The shape, in three parts:

- **`screen_bytes` runs at fetch time** (fetch_poi_images.py calls it in
  `store_photo`), because that is the one moment the image bytes are
  guaranteed to be in hand. The result travels inside the photo record in
  poi_images.json, so a carry-forward run never re-screens.
- **The decisions ledger** (reference/photo_screen_decisions.json) records
  what a person concluded about each flagged photo, keyed by the same
  content digest that names the bytes everywhere else (lib/photo_store.py).
  Keying by digest means a decision survives the photo moving between POIs,
  and re-fetching identical bytes cannot re-ask an answered question. It
  lives in reference/ because each row IS a reviewed judgement - exactly the
  bar .github/tests/test_no_committed_data.py sets for that directory.
- **`gate_photos` runs at export time** (export_poi.py, Commons photos
  only): a photo the screen flagged and nobody has looked at is held out of
  the export; one a person refused stays out permanently; everything else
  ships. Holding at export rather than at fetch is deliberate - the fetch
  keeps recording what exists, so clearing a photo publishes it on the next
  export with no re-crawl.

The detector is OpenCV's stock Haar frontal-face cascade, chosen over a DNN
detector for one reason: the cascade XML ships inside the
opencv-python-headless wheel (pinned <5 - see requirements.in), so the
check adds no model download to a pipeline that fetches nothing it does not
pin. It is a weak detector and that is priced in: it misses profiles,
occlusions and small faces, and a miss here means we republish a photo
Commons already publishes - bounded harm, backed by the report-this-photo
path on the card. The failure this gate exists to prevent is the confident
one: shipping a stranger's face because no one ever looked.

Wiring check, so "the cascade detects faces at the sizes we fetch" is
measured rather than assumed (2026-08-20, opencv-python-headless 4.14.0.94):
against the 500px Commons thumbnail of a portrait
(File:President Barack Obama.jpg) `detect_faces` returns 1; on a flat gray
JPEG and on a drawn cartoon face it returns 0. The pipeline fetches 640px
thumbnails (fetch_poi_images.IMAGE_WIDTH_PX), the same order of size.

Pure module except for the ledger I/O - no network, and cv2 is imported
lazily so every pipeline script that imports export_poi does not pay for
OpenCV unless a screen actually runs.
"""

import json
import os
from datetime import date
from pathlib import Path

from lib.photo_store import photo_key

DECISIONS_PATH = Path(__file__).parent.parent / "reference" / "photo_screen_decisions.json"

# Names the detector inside each screen result, so a future better screener
# can tell its own results from this one's and re-screen only what the old
# one screened.
SCREENER = "haar_frontalface_default"

# @unvalidated - these are OpenCV's tutorial defaults, not values tuned on
# the corridor corpus. What would settle them: run the screen over a full
# Commons crawl and count what the review page shows - flags that are not
# faces (lower MIN_NEIGHBORS was too jumpy) or faces the export shipped
# unflagged (raise the issue, not the constant: the cascade itself is the
# ceiling). Until then they lean sensitive on purpose - an extra flag costs
# one human glance, a miss costs a stranger's face on every phone.
SCALE_FACTOR = 1.1
MIN_NEIGHBORS = 5
MIN_FACE_PX = 40


def detect_faces(image_bytes: bytes) -> int | None:
    """How many frontal faces the cascade finds, or None when the bytes do
    not decode as an image at all.

    None rather than a raise or a zero, because both neighbours are wrong:
    raising would kill a forty-minute crawl over one corrupt thumbnail, and
    zero would record "screened, no faces" about a photo nothing ever
    looked at. None is "could not screen", which the gate counts and passes
    (an unscreenable photo is the same case as one fetched before this
    check existed - see gate_photos)."""
    import cv2
    import numpy as np

    gray = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return None
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(
        gray, scaleFactor=SCALE_FACTOR, minNeighbors=MIN_NEIGHBORS, minSize=(MIN_FACE_PX, MIN_FACE_PX)
    )
    return len(faces)


def screen_bytes(image_bytes: bytes) -> dict:
    """The screen record that travels inside a photo record: what was found,
    by which detector, when. `faces: null` in the JSON means the bytes did
    not decode - screened-and-clear is always an explicit 0."""
    return {"faces": detect_faces(image_bytes), "screener": SCREENER, "on": date.today().isoformat()}


def flagged(photo: dict) -> bool:
    """Whether this photo record's screen affirmatively found a face.

    Unscreened is not flagged: a record with no screen at all (fetched
    before #836) or a screen whose decode failed (faces: null) has nothing
    affirmative in it, and holding those would quietly unpublish the whole
    pre-existing corpus the day this shipped."""
    return bool(photo.get("screen", {}).get("faces"))


def load_decisions(path: Path = DECISIONS_PATH) -> dict[str, dict]:
    """The human decisions ledger, keyed by photo digest. A missing file is
    an empty ledger. An unknown decision value raises: this file is
    hand-adjacent (written by review_flagged_photos.py, edited in review),
    and a typo like "clear" silently treated as not-cleared would hold a
    photo somebody explicitly released."""
    if not path.exists():
        return {}
    decisions = json.loads(path.read_text(encoding="utf-8")).get("decisions", {})
    for digest, entry in decisions.items():
        if entry.get("decision") not in ("cleared", "refused"):
            raise ValueError(f"{path.name}: decision for {digest} is {entry.get('decision')!r}, expected 'cleared' or 'refused'")
    return decisions


def record_decision(digest: str, decision: str, note: str | None = None, path: Path = DECISIONS_PATH) -> None:
    """Write one decision into the ledger, latest-wins, atomically.

    Sorted keys and indented output on purpose: this file is committed, and
    its diff is the review of the judgement each row encodes - one decision
    changed must read as one row changed."""
    if decision not in ("cleared", "refused"):
        raise ValueError(f"decision must be 'cleared' or 'refused', not {decision!r}")
    # For its digest validation alone: a truncated paste recorded as a key
    # would sit in the ledger deciding nothing, forever.
    photo_key(digest)
    load_decisions(path)  # validation only - refuse to build on a corrupt ledger
    # Read the whole document rather than just the decisions, because the
    # file carries a _README a rewrite must not eat.
    document = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    entry: dict = {"decision": decision, "on": date.today().isoformat()}
    if note:
        entry["note"] = note
    document.setdefault("decisions", {})[digest] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def unpublishable_digests(outcome_path: Path, decisions: dict[str, dict]) -> set[str]:
    """Digests whose bytes may not sit in the public bucket: refused, or
    flagged with nobody's decision yet.

    The export gate alone is not enough, because publish.py uploads every
    cached photo and an object's key being unguessable does not make it
    private - `photos/<digest>.jpg` is a public URL the moment anything
    leaks the digest, and the outcome JSONs that carry the digests are
    themselves published as sidecars (#465). So a held photo is held from
    the bucket, not merely from the cards; clearing it publishes bytes and
    reference together on the next run. A refusal recorded after an upload
    still needs the object deleted by hand - this only stops the door, it
    does not empty the room - which review_flagged_photos.py says when a
    refusal lands."""
    if not outcome_path.exists():
        return set()
    outcomes = json.loads(outcome_path.read_text(encoding="utf-8")).get("pois", {})
    held = set()
    for record in outcomes.values():
        if record.get("status") != "found":
            continue
        photos = record["photos"] if "photos" in record else ([record["photo"]] if "photo" in record else [])
        for photo in photos:
            digest = photo.get("digest")
            if not digest:
                continue
            decision = decisions.get(digest, {}).get("decision")
            if decision == "refused" or (flagged(photo) and decision != "cleared"):
                held.add(digest)
    return held


def gate_photos(photos: dict[str, list[dict]], decisions: dict[str, dict]) -> tuple[dict[str, list[dict]], dict[str, int]]:
    """The export-time gate: the same {poi_id: [photos]} shape in and out,
    minus what may not ship yet, plus the counts the export log prints.

    Per photo: refused stays out permanently, whatever the screen said;
    flagged with no decision is held for review_flagged_photos.py; flagged
    and cleared ships; screened-clear ships; unscreened ships and is
    counted, because unscreened is a fact about when the photo was fetched,
    not about what is in it. Counts exist so a nonzero hold is a line in
    the export log rather than a silent shrink of the photo set."""
    counts = {"shipped": 0, "held": 0, "refused": 0, "unscreened": 0}
    gated: dict[str, list[dict]] = {}
    for poi_id, poi_photos in photos.items():
        kept = []
        for photo in poi_photos:
            decision = decisions.get(photo.get("digest", ""), {}).get("decision")
            if decision == "refused":
                counts["refused"] += 1
                continue
            if flagged(photo) and decision != "cleared":
                counts["held"] += 1
                continue
            if "screen" not in photo or photo.get("screen", {}).get("faces") is None:
                counts["unscreened"] += 1
            kept.append(photo)
            counts["shipped"] += 1
        if kept:
            gated[poi_id] = kept
    return gated, counts
