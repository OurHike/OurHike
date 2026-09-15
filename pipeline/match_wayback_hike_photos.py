"""Match each recovered NYNJTC photograph to the hike it belongs to (#1450).

    python match_wayback_hike_photos.py              the sheet and the scores
    python match_wayback_hike_photos.py --min 0.55   move the confidence floor

Input is `fetch_wayback_hike_photos.py`'s recovery and `fetch_hikefinder.py`'s
385 hikes. Output is a REVIEW SHEET, not an artifact: every proposed pairing
rendered with the photograph beside the hike it was matched to, the score, and
the exact words the score rests on, for a person to confirm or reject. Only
confirmed rows belong in `pipeline/reference/`, which CONTRIBUTING.md reserves
for "a join that encodes judgement somebody reviews row by row".

WHY A SHEET AND NOT A THRESHOLD. features/POI_PHOTOS.md's 2026-08-08
measurement is the argument: the card for Gravel Springs Hut Shelter would
have shown an Asiatic dayflower, and that photograph passed every automatic
bar there was - recent, openly licensed, geotagged, creditable. A score is a
claim about strings. Whether a photograph is OF a hike is a claim about the
world, and nothing in this file can settle it.

**THE SCORE IS REPORTED, NEVER OBEYED.** `--min` moves what the sheet puts
above the fold; it does not decide anything. A row nobody confirmed ships no
photograph, at any score.

THE THREE SIGNALS, in the order the maintainer named them:

  - **Description.** The hike's prose names the landmarks the walk passes, and
    NYNJTC named each photograph after the thing in it. "Beaver Lodge in swamp
    on Terrace Pond South Trail" meets a write-up that says "Terrace Pond
    South Trail" and the pair is the same walk. This is the strongest signal
    because both sides were written by the same people about the same ground.
  - **Location.** A photograph carries no coordinate, so location enters as
    CORROBORATION rather than as a match: a landmark that agrees with the
    hike's park or region is worth more than the same landmark floating free,
    and a landmark whose only support is the park is worth little, because a
    park holds dozens of these hikes.
  - **Name.** The hike's own title, which is usually its landmark - "Terrace
    Pond North Loop", "Mt. Minsi Loop". A photograph naming a hike's title
    landmark is the cleanest evidence available here.

WHAT MAKES A WORD DISTINCTIVE, and this is where a naive matcher fails. Every
one of these filenames contains "trail", "view", "bridge", "lake" or
"mountain"; so does every hike. Matching on those would pair everything with
everything and report it as coverage. `distinctive_terms()` keeps the words
that separate one place from another - "Terrace", "Wawayanda", "Minsi" - and
a pairing supported by nothing else scores zero rather than low.

WHAT A TRIAL SAID, 2026-09-15. Run over the first 25 recovered subjects
against twelve hikes written in the export's shape, the ranking held: the top
eight were all correct, including "Anthony's Nose from the Major Welch Trail
along Hessian Lake" onto the Major Welch hike at 6.40 and "Beaver Lodge in
swamp on Terrace Pond South Trail" onto Terrace Pond at 4.40. The two wrong
answers both scored under 2.2 and both rest on a single weak signal - one
shared word ("black", from "Black Rock" onto "Black Creek"), and one shared
phrase that names a feature rather than a place ("beaver lodge", which
several of these hikes pass). That is the whole argument for DEFAULT_MIN_SCORE
below, and for the sheet.

SCORING IS ORDINAL, NOT A PROBABILITY. The number is a rank, so a reviewer
meets the likeliest rows first; it is not "73% likely to be correct" and
nothing here has been calibrated against a confirmed set, because there is no
confirmed set until somebody works this sheet. `@unvalidated` in that precise
sense: the WEIGHTS below are picked, and what would settle them is the first
few dozen confirmed rows - at which point the sheet becomes its own training
data and these can be fitted rather than guessed.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
PHOTOS_PATH = RAW_DIR / "wayback_hike_photos.json"
HIKES_PATH = RAW_DIR / "hikefinder.json"
SHEET_PATH = PROCESSED_DIR / "wayback_photo_review.html"
PROPOSED_PATH = PROCESSED_DIR / "wayback_photo_matches.json"

#: Where a confirmed join belongs. Written by a person working the sheet, not
#: by this script - CONTRIBUTING.md's line ceiling on reference/ exists
#: because everything in it is meant to have been read row by row.
REFERENCE_PATH = ROOT / "reference" / "nynjtc_hike_photos.json"

#: Words every hike and every photograph in this corpus shares. Keeping them
#: would pair everything with everything: 403 photographs against 385 hikes is
#: 155,155 candidate pairs, and "trail" appears on both sides of most of them.
#:
#: Read off the real corpus rather than imagined - these are the words that
#: actually recur in the 403 filenames.
GENERIC_TERMS = frozenset(
    """
    trail trails hike hikes loop loops walk path road roads route
    view views viewpoint vista overlook lookout
    mountain mountains mount mt hill hills ridge ridges peak summit
    lake lakes pond ponds river creek brook stream swamp wetland falls fall
    bridge boardwalk steps stairs cave rock rocks boulder boulders
    park forest woods state county section area preserve
    north south east west upper lower old new near start end
    the and from with along near over under into
    photo picture image copy jpg jpeg
    winter summer spring autumn fall snow
    """.split()
)

#: How much each signal contributes. @unvalidated - picked to rank, not
#: calibrated, and the docstring says what would settle them.
#:
#: The NAME weight leads because a hike's title is chosen to identify it, so a
#: landmark shared with the title is the least ambiguous evidence here. The
#: DESCRIPTION weight is close behind and does most of the work in practice,
#: because a title carries one landmark and a write-up carries a dozen. PARK
#: is deliberately small: a park holds dozens of these hikes, so park
#: agreement corroborates a landmark and can never carry a pairing alone -
#: which `score_pair()` enforces structurally rather than by weight.
NAME_WEIGHT = 1.0
DESCRIPTION_WEIGHT = 0.8
PARK_WEIGHT = 0.15
REGION_WEIGHT = 0.05

#: A multi-word landmark ("Terrace Pond", "Major Welch") is far better
#: evidence than one word, because two distinctive words colliding by accident
#: is rare where one is routine.
PHRASE_BONUS = 0.5

#: What the sheet puts above the fold. NOT a gate - see the docstring.
#:
#: MEASURED, 2026-09-15, on a trial of the first 25 recovered subjects against
#: twelve hand-written hikes in the export's shape. Every pairing at 3.6 and
#: above was correct; every pairing below 2.2 that a person checked was wrong,
#: and the two failures are worth naming because they are the shape of the
#: error rather than bad luck:
#:
#:   1.80  "Black Rock from Mt. Misery"      -> Black Creek Preserve Loop
#:   2.10  "Beaver lodge"                    -> Terrace Pond North Loop
#:
#: The first shares one word, "black", with a different place. The second
#: shares a real phrase that is a FEATURE and not a place - several of these
#: hikes pass a beaver lodge. Both are what a single weak signal looks like.
#:
#: 2.5 sits between the two bands rather than on either, which is the most a
#: trial this size supports. @unvalidated as a general figure: 25 subjects
#: against 12 invented hikes is a shape check, not the 403-against-385 run,
#: and what would settle it is the first sheet somebody works.
DEFAULT_MIN_SCORE = 2.5

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]+")


@dataclass
class Photo:
    digest: str
    subject: str
    filename: str
    credit: str | None
    width: int | None
    height: int | None
    original_url: str
    timestamp: str

    @property
    def terms(self) -> set[str]:
        return distinctive_terms(self.subject)

    @property
    def frame(self) -> str:
        """Which frame the card would give it - the decision #1450's Phase 3
        labelling and the maintainer's "picks frame from natural size" both
        rest on. A 250px rendition in a hero box is a 2.1x upscale cropped to
        16:10; at its native size it is simply a smaller, honest picture."""
        if self.width is None:
            return "unknown"
        return "hero" if self.width >= 640 else "inset"


@dataclass
class Hike:
    hike_id: str
    name: str
    park: str
    region: str
    description: str
    lat: float | None
    lon: float | None

    @property
    def name_terms(self) -> set[str]:
        return distinctive_terms(self.name)

    @property
    def description_terms(self) -> set[str]:
        return distinctive_terms(self.description)

    @property
    def park_terms(self) -> set[str]:
        return distinctive_terms(self.park)

    @property
    def region_terms(self) -> set[str]:
        return distinctive_terms(self.region)


@dataclass
class Pairing:
    photo: Photo
    hike: Hike
    score: float
    #: The exact words the score rests on, per signal, so a reviewer can see
    #: WHY rather than being handed a number. A pairing whose reasons a person
    #: cannot read is a pairing they cannot reject on the merits.
    on_name: set[str] = field(default_factory=set)
    on_description: set[str] = field(default_factory=set)
    on_park: set[str] = field(default_factory=set)
    phrases: set[str] = field(default_factory=set)

    @property
    def carried_by_park_alone(self) -> bool:
        """A pairing with nothing but park agreement behind it. Refused rather
        than ranked low: a park holds dozens of these hikes, so "same park" is
        not evidence about WHICH hike, and a sheet full of them would bury the
        rows worth reading."""
        return not (self.on_name or self.on_description)


def distinctive_terms(text: str | None) -> set[str]:
    """The words in `text` that could tell one place from another."""
    if not text:
        return set()
    return {word.lower() for word in _WORD_RE.findall(text) if len(word) > 2 and word.lower() not in GENERIC_TERMS}


def shared_phrases(subject: str, target: str) -> set[str]:
    """Adjacent distinctive word pairs present in both, lowercased.

    "Terrace Pond" surviving on both sides is worth more than "terrace" and
    "pond" each surviving somewhere, because the words being ADJACENT is what
    makes them a place's name rather than two coincidences.
    """
    if not subject or not target:
        return set()

    def bigrams(text: str) -> set[str]:
        words = [w.lower() for w in _WORD_RE.findall(text)]
        found = set()
        for first, second in zip(words, words[1:]):
            if first in GENERIC_TERMS and second in GENERIC_TERMS:
                continue
            if len(first) > 2 and len(second) > 2:
                found.add(f"{first} {second}")
        return found

    return bigrams(subject) & bigrams(target)


def score_pair(photo: Photo, hike: Hike) -> Pairing | None:
    """How well this photograph's subject matches this hike, or None.

    None rather than zero for a pairing with no distinctive support at all:
    155,155 candidate pairs exist and the sheet is for the ones worth a
    person's time.
    """
    terms = photo.terms
    if not terms:
        return None

    on_name = terms & hike.name_terms
    on_description = terms & hike.description_terms
    on_park = terms & hike.park_terms
    on_region = terms & hike.region_terms

    phrases = shared_phrases(photo.subject, hike.name) | shared_phrases(photo.subject, hike.description)

    score = (
        NAME_WEIGHT * len(on_name)
        + DESCRIPTION_WEIGHT * len(on_description)
        + PARK_WEIGHT * len(on_park)
        + REGION_WEIGHT * len(on_region)
        + PHRASE_BONUS * len(phrases)
    )
    if score <= 0:
        return None

    pairing = Pairing(photo, hike, score, on_name, on_description, on_park, phrases)
    if pairing.carried_by_park_alone:
        return None
    return pairing


def best_pairings(photos: list[Photo], hikes: list[Hike]) -> dict[str, list[Pairing]]:
    """Every photograph's candidate hikes, best first.

    Candidates are kept rather than only the winner, because the sheet's job
    is to let a person choose - and a photograph whose top two candidates are
    a point apart is exactly the row where the automatic answer is least
    trustworthy and a human is most useful.
    """
    ranked: dict[str, list[Pairing]] = {}
    for photo in photos:
        found = [p for p in (score_pair(photo, hike) for hike in hikes) if p is not None]
        found.sort(key=lambda p: -p.score)
        ranked[photo.digest] = found[:5]
    return ranked


def load_photos(path: Path | None = None) -> list[Photo]:
    path = path or PHOTOS_PATH
    if not path.exists():
        return []
    document = json.loads(path.read_text(encoding="utf-8"))
    return [
        Photo(
            digest=row["digest"],
            subject=row.get("subject", ""),
            filename=row.get("filename", ""),
            credit=row.get("credit"),
            width=row.get("width"),
            height=row.get("height"),
            original_url=row.get("original_url", ""),
            timestamp=row.get("timestamp", ""),
        )
        for row in document.get("photos", [])
    ]


def load_hikes(path: Path | None = None) -> list[Hike]:
    """The export's hikes, flattened to the fields this match reads.

    `description` is joined from the write-up's paragraphs because a landmark
    can appear in any of them, and the export stores them as a list.
    """
    path = path or HIKES_PATH
    if not path.exists():
        return []
    cache = json.loads(path.read_text(encoding="utf-8")).get("hikes") or {}
    hikes = []
    for key, row in cache.items():
        start = row.get("start") or {}
        description = row.get("description")
        if isinstance(description, list):
            description = " ".join(str(part) for part in description)
        hikes.append(
            Hike(
                hike_id=str(key),
                name=row.get("name") or "",
                park=row.get("park") or "",
                region=row.get("region") or "",
                description=description or "",
                lat=start.get("lat"),
                lon=start.get("lon"),
            )
        )
    return hikes


def _reasons(pairing: Pairing) -> str:
    parts = []
    if pairing.phrases:
        parts.append("phrase: " + ", ".join(sorted(pairing.phrases)))
    if pairing.on_name:
        parts.append("name: " + ", ".join(sorted(pairing.on_name)))
    if pairing.on_description:
        parts.append("description: " + ", ".join(sorted(pairing.on_description)))
    if pairing.on_park:
        parts.append("park: " + ", ".join(sorted(pairing.on_park)))
    return " | ".join(parts) or "nothing distinctive"


def write_sheet(ranked: dict[str, list[Pairing]], photos: list[Photo], minimum: float, path: Path) -> None:
    """The sheet a person works.

    The photograph is rendered from the content-addressed store next to the
    hike, because #1450's standard is what a person confirms and nobody can
    confirm a pairing they cannot see. Same shape as
    `hikefinder_routes_review.html`, for the same reason.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    by_digest = {p.digest: p for p in photos}
    rows = []
    strong = weak = unmatched = 0

    for digest, candidates in sorted(ranked.items(), key=lambda kv: -(kv[1][0].score if kv[1] else 0)):
        photo = by_digest[digest]
        if not candidates:
            unmatched += 1
            continue
        top = candidates[0]
        if top.score >= minimum:
            strong += 1
        else:
            weak += 1
        alternatives = "".join(
            f"<li>{html.escape(c.hike.name)} <span class=s>{c.score:.2f}</span> "
            f"<span class=w>{html.escape(_reasons(c))}</span></li>"
            for c in candidates[1:]
        )
        rows.append(
            f"""<tr class="{"strong" if top.score >= minimum else "weak"}">
  <td><img src="../raw/poi_photos/{html.escape(digest)}.jpg" alt=""
           title="{html.escape(photo.filename)}"></td>
  <td><div class=subj>{html.escape(photo.subject)}</div>
      <div class=w>{html.escape(photo.filename)}</div>
      <div class=w>{photo.width}&times;{photo.height} &middot; {html.escape(photo.frame)} frame
      &middot; {"credit: " + html.escape(photo.credit) if photo.credit else "no credit in filename"}</div></td>
  <td><div class=hike>{html.escape(top.hike.name)}</div>
      <div class=w>{html.escape(top.hike.park)} &middot; {html.escape(top.hike.region)}</div>
      <div class=score>{top.score:.2f}</div>
      <div class=w>{html.escape(_reasons(top))}</div>
      <ul class=alt>{alternatives}</ul></td>
</tr>"""
        )

    document = f"""<!doctype html><meta charset=utf-8>
<title>NYNJTC archive photos - review</title>
<style>
 body{{font:14px/1.45 system-ui,sans-serif;margin:24px;color:#222;background:#fafafa}}
 table{{border-collapse:collapse;width:100%}}
 td{{border-top:1px solid #ddd;padding:10px;vertical-align:top}}
 img{{width:180px;height:auto;border-radius:6px;background:#eee}}
 .subj{{font-weight:600}} .hike{{font-weight:600;color:#14532d}}
 .score{{font-variant-numeric:tabular-nums;color:#555}}
 .w{{color:#666;font-size:12px}} .s{{color:#555;font-variant-numeric:tabular-nums}}
 .alt{{margin:6px 0 0;padding-left:18px;color:#666;font-size:12px}}
 .weak{{background:#fff8f0}}
 .note{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:14px;margin-bottom:18px}}
</style>
<h1>NYNJTC archive photographs, matched to hikes</h1>
<div class=note>
<p><strong>{strong}</strong> photographs have a candidate at or above {minimum:.2f};
<strong>{weak}</strong> below it; <strong>{unmatched}</strong> match nothing distinctive.</p>
<p><strong>The score is a rank, not a probability.</strong> It has not been calibrated
against any confirmed set, because there is no confirmed set until this sheet is worked.
Nothing here ships until a row is confirmed into <code>reference/nynjtc_hike_photos.json</code>
by hand &mdash; a photograph that passes every automatic bar can still be of the wrong place,
which is exactly what the Asiatic dayflower on Gravel Springs Hut Shelter was.</p>
<p>Shaded rows fall below the line and are shown anyway: a low score on a correct pairing
is a fact about this matcher, not about the photograph.</p>
</div>
<table>{"".join(rows)}</table>
"""
    path.write_text(document, encoding="utf-8")


def main(minimum: float) -> int:
    photos = load_photos()
    if not photos:
        print(f"Missing {PHOTOS_PATH} - run fetch_wayback_hike_photos.py first.")
        return 1

    hikes = load_hikes()
    if not hikes:
        print(f"Missing {HIKES_PATH} - run fetch_hikefinder.py first.")
        print()
        print("That fetch needs HIKEFINDER_PASSWORD, which is a GitHub Actions secret")
        print("(.github/expected-settings.yml) and so is not readable from a sandbox.")
        print("This match runs where the secret is injected, not on a laptop.")
        return 1

    print(f"{len(photos)} photographs against {len(hikes)} hikes ...")
    ranked = best_pairings(photos, hikes)

    tops = [c[0] for c in ranked.values() if c]
    strong = [p for p in tops if p.score >= minimum]
    unmatched = sum(1 for c in ranked.values() if not c)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    PROPOSED_PATH.write_text(
        json.dumps(
            {
                "min_score": minimum,
                "note": "Proposed, not confirmed. reference/nynjtc_hike_photos.json is the confirmed join.",
                "matches": [
                    {
                        "digest": p.photo.digest,
                        "hike_id": p.hike.hike_id,
                        "hike_name": p.hike.name,
                        "score": round(p.score, 3),
                        "subject": p.photo.subject,
                        "credit": p.photo.credit,
                        "frame": p.photo.frame,
                        "reasons": _reasons(p),
                    }
                    for p in sorted(tops, key=lambda p: -p.score)
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_sheet(ranked, photos, minimum, SHEET_PATH)

    print()
    print(f"  at or above {minimum:.2f}      {len(strong)}")
    print(f"  below it                {len(tops) - len(strong)}")
    print(f"  nothing distinctive     {unmatched}")
    hikes_covered = len({p.hike.hike_id for p in strong})
    print(f"  distinct hikes reached  {hikes_covered} of {len(hikes)}")
    print()
    print(f"  sheet     {SHEET_PATH}")
    print(f"  proposed  {PROPOSED_PATH}")
    print()
    print("  NOTHING SHIPS FROM THIS FILE. A confirmed row lives in")
    print(f"  {REFERENCE_PATH.relative_to(ROOT)}, written by a person working the sheet.")
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--min",
        dest="minimum",
        type=float,
        default=DEFAULT_MIN_SCORE,
        help="What the sheet puts above the fold. Ranks; decides nothing.",
    )
    args = parser.parse_args(argv)
    return main(args.minimum)


if __name__ == "__main__":
    raise SystemExit(run())
