"""Match each recovered NYNJTC photograph to the hike it belongs to (#1450).

    python match_wayback_hike_photos.py              the sheet and the scores
    python match_wayback_hike_photos.py --min 0.55   move the confidence floor

Input is `fetch_wayback_hike_pages.py`'s write-ups, `fetch_wayback_hike_photos.py`'s
recovery, and `fetch_hikefinder.py`'s 385 hikes. Output is a REVIEW SHEET, not
an artifact: every proposed pairing
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
above the fold, and only among the rows a score decides at all - a row the
archive's own write-up placed leads the sheet whatever `--min` says. Neither
decides anything: a row nobody confirmed ships no photograph, at any score.

THE SIGNALS, STRONGEST FIRST. The order changed on 2026-09-15, when the
maintainer asked whether this was matching on name and said to try location
and distance first. It was matching on name, and the reorder below is the
answer: the strongest signal is not a signal at all but a fact that was
sitting in the archive unread.

  1. **THE PAGE JOIN - a fact, not a score.** Each archived write-up SHOWS its
     own photographs, so `HikePage.photos` names the very files
     `fetch_wayback_hike_photos.py` recovered. A photograph whose filename
     appears on a write-up belongs to that write-up. Nothing is inferred and
     no string is compared: NYNJTC published the pairing and the archive kept
     it. This resolves photograph -> NYNJTC hike outright, and leaves only
     NYNJTC hike -> export hike, which is a far easier question because both
     sides are now the same organisation's own titles and coordinates.
  2. **NAME, between the write-up and the export.** Both are NYNJTC's title
     for the same walk, so the expected case is that they are the same string
     once punctuation is set aside - the maintainer's bet, in their words,
     that "you will even find that the names match then". `normalise_title()`
     is the whole of what is forgiven, and it is deliberately small.
  3. **DISTANCE, between the write-up's coordinate and the export's start.**
     It NARROWS, it never decides. Two distinct hikes routinely share a
     parking lot, so proximity cannot say WHICH hike - it can only rank
     candidates that already agree by name, and `resolve_page()` refuses a
     pairing carried by distance alone for exactly the reason `score_pair()`
     refuses one carried by park alone.
  4. **THE PHOTOGRAPH'S SUBJECT, scored against the hike's prose.** What this
     file did first and now does last: the fallback for a photograph whose
     write-up was never recovered. Unchanged below, and still the only route
     available for those.

A photograph reached by route 1 and a photograph reached by route 4 are not
comparable on a number, so they are NOT put on one number. `BASIS_ORDER`
ranks the routes and the text score ranks within them, which is why the sheet
shows a basis column: a reviewer confirming a row should be able to see that
NYNJTC itself put the photograph on that page, rather than reading it as a
strong string match.

WHERE THE TWO DISAGREE IS THE MOST VALUABLE ROW ON THE SHEET. When the page
join lands on one hike and the text score prefers another, the sheet says so
and puts it up top. That is either the text matcher being wrong in a way worth
seeing, or a write-up reusing a photograph, and both are things a person
should look at before anything ships.

WHAT MAKES A WORD DISTINCTIVE, and this is where a naive matcher fails. Every
one of these filenames contains "trail", "view", "bridge", "lake" or
"mountain"; so does every hike. Matching on those would pair everything with
everything and report it as coverage. `distinctive_terms()` keeps the words
that separate one place from another - "Terrace", "Wawayanda", "Minsi" - and
a pairing supported by nothing else scores zero rather than low.

WHAT A TRIAL SAID ABOUT ROUTE 4, 2026-09-15 - and route 4 only, because the
write-ups had not been recovered yet when it ran. Run over the first 25 recovered subjects
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

from lib.hikefinder import metres_between

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
PHOTOS_PATH = RAW_DIR / "wayback_hike_photos.json"

#: Where the recovered bytes are, which is NOT the published photo store -
#: see fetch_wayback_hike_photos.ARCHIVE_STORE_DIRNAME for why. The sheet
#: renders from here, so a reviewer sees the photograph without it ever
#: having been somewhere `publish.py` would sweep it up.
ARCHIVE_STORE_DIRNAME = "wayback_photos"
PAGES_PATH = RAW_DIR / "wayback_hike_pages.json"
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

#: How a pairing was reached, worst last. The sheet sorts on this BEFORE the
#: score, because the routes are not commensurable: a photograph NYNJTC itself
#: printed on a hike's page is better evidence than any number a string
#: comparison can produce, and averaging the two into one figure would hide
#: exactly the distinction a reviewer needs.
BASIS_PAGE_NAME = "page + title"
BASIS_PAGE_NEAR = "page + nearby title"
BASIS_PAGE_ONLY = "page, hike unplaced"
BASIS_SUBJECT = "subject text"
BASIS_ORDER = (BASIS_PAGE_NAME, BASIS_PAGE_NEAR, BASIS_SUBJECT, BASIS_PAGE_ONLY)

#: The routes that put a photograph on a hike the export actually has, and so
#: the only two a shipped row can come from.
#:
#: BASIS_PAGE_ONLY sits at the BOTTOM of the order above, under even the
#: weakest text match, and the first draft had it third - above every text row
#: - which was wrong in a way worth recording. A page-only row is CERTAIN
#: about its NYNJTC write-up and has no export hike behind it, so it is the
#: one row on the sheet that definitionally cannot produce a photograph on a
#: card. Ranking certainty above usefulness would have buried every correct
#: text match under rows whose best outcome is a person deciding there is
#: nothing to do.
BASIS_PLACED = (BASIS_PAGE_NAME, BASIS_PAGE_NEAR)

#: How far a write-up's coordinate may sit from an export hike's start before
#: they stop being candidates for the same walk.
#:
#: @unvalidated, and deliberately GENEROUS rather than tight. Nobody has yet
#: seen what these coordinates point at: a trailhead marker would put the same
#: walk within a couple of hundred metres, while a coordinate geocoded to the
#: park would sit kilometres off and a tight bound would silently drop correct
#: rows - the expensive failure, because a dropped row looks identical to a
#: photograph nobody could place.
#:
#: Being generous is affordable only because distance NEVER decides alone:
#: `resolve_page()` requires title agreement as well, so widening this costs
#: ranking rather than correctness. What would settle it is the distribution
#: of these distances over the first few dozen rows somebody confirms - at
#: which point it can be set to what the data shows instead of to what a wrong
#: answer would cost.
MAX_JOIN_METRES = 5_000.0

#: The only differences between an archived title and an export title that are
#: forgiven, beyond case and punctuation. Small on purpose: every entry is a
#: claim that two strings mean the same walk, and the real index run is what
#: will show which variations actually occur. @unvalidated - these are the
#: abbreviations visible in the corpus already, not a surveyed list.
_TITLE_ALIASES = {
    "mt": "mount",
    "mtn": "mountain",
    "st": "state",
    "pk": "park",
    "rd": "road",
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
}

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]+")
_TITLE_NOISE_RE = re.compile(r"[^a-z0-9]+")
_APOSTROPHE_RE = re.compile(r"[\u2019']")


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
class PagePhoto:
    """One photograph a write-up showed, as that fetcher recorded it.

    Mirrors `fetch_wayback_hike_pages.PagePhoto` rather than importing it,
    the same way `Photo` and `Hike` mirror their producers: this module reads
    a cache file, and a shape it reconstructs from JSON is the shape it can
    actually rely on.
    """

    filename: str
    credit: str | None
    credit_basis: str | None


@dataclass
class Page:
    """One archived NYNJTC write-up, as `fetch_wayback_hike_pages.py` cached it.

    `photos` is the join and the reason this class exists: it holds the u26
    filenames the page displayed, which are the same filenames the photograph
    recovery stores. Everything else here is what places that page among the
    export's hikes.
    """

    url: str
    timestamp: str
    name: str
    park: str | None
    region: str | None
    lat: float | None
    lon: float | None
    description: str
    photos: list[PagePhoto]

    @property
    def where(self) -> tuple[float, float] | None:
        return (self.lat, self.lon) if self.lat is not None and self.lon is not None else None


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
    #: WHICH ROUTE reached this pairing - see BASIS_ORDER. Carried on the
    #: pairing rather than worked out by the sheet so that the proposed JSON,
    #: the sheet and anything a person later writes into reference/ all record
    #: the same answer to "how do we think we know this".
    basis: str = BASIS_SUBJECT
    #: The archived write-up this photograph appeared on, when there was one.
    page: Page | None = None
    #: ...and that page's record OF THIS PHOTOGRAPH, which is where the
    #: licence's required credit lives.
    shown_as: PagePhoto | None = None
    #: Metres between that write-up's coordinate and the hike's start, when
    #: both had one. Reported, never thresholded on its own.
    metres: float | None = None

    @property
    def rank(self) -> tuple[int, float]:
        """Sort key: route first, score within it. The routes are ordinal and
        the score is ordinal, and neither is a probability."""
        return (BASIS_ORDER.index(self.basis), -self.score)

    @property
    def from_page(self) -> bool:
        """A write-up published this photograph, whatever came of it."""
        return self.page is not None

    @property
    def placed_by_page(self) -> bool:
        """...and that write-up was matched to a hike the export has. The
        only rows that can ever ship."""
        return self.basis in BASIS_PLACED

    @property
    def credit(self) -> str | None:
        """The photographer this photograph may be published under, or None.

        Two places name one: the write-up that printed it, and the filename
        NYNJTC gave it. The page wins when it has one, because
        `nynjtc_hikes_licence` asks for "the credit line the page carries"
        and that is literally it.

        AND BOTH NEED A PAGE. The filename route's whole justification is
        that NYNJTC wrote the photographer into the file name and a write-up
        published that name in its `src` - so with no recovered write-up
        behind the photograph there is no page carrying anything, and the
        justification is an empty sentence. The first version accepted it
        anyway, which review caught: a photograph no write-up showed could
        reach the proposed file on a licence worded "the credit line the page
        carries". It cannot now.
        """
        if self.shown_as is not None and self.shown_as.credit:
            return self.shown_as.credit
        return self.photo.credit if self.page is not None else None

    @property
    def credit_basis(self) -> str | None:
        """Where that name was read, or None when there is no name.

        Carried separately because the two are not equally strong. A page
        credit is the licence's own wording. A FILENAME credit is a judgement
        this build is making and should be visible as one: NYNJTC wrote the
        photographer into the file name and the page published that name in
        its `src`, so the page does credit the photograph - but only just, and
        a reviewer who reads the condition more strictly should be able to see
        which rows rest on it and refuse them. Nine of 403 recovered
        photographs are in that position (measured, fetch_wayback_hike_photos).
        """
        if self.shown_as is not None and self.shown_as.credit:
            return f"page, {self.shown_as.credit_basis}"
        return "filename" if self.credit else None

    @property
    def publishable(self) -> bool:
        """THE LICENCE GATE (#1504), and the only bar here that is not about
        whether the pairing is RIGHT.

        `sources.json`'s `nynjtc_hikes_licence` makes attribution "a condition
        rather than a courtesy ... a photograph the page does not credit is
        not fetched at all". The recovery this feeds selected by directory
        prefix and so has photographs the permission does not cover; this is
        where they stop. A row that fails here is still shown on the sheet -
        so the size of the gap is visible rather than quietly subtracted - but
        it cannot lead the sheet and cannot reach the proposed file.
        """
        return self.credit is not None

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


def normalise_title(title: str | None) -> str:
    """A title reduced to what two spellings of the same walk share.

    Case, punctuation and the abbreviations in `_TITLE_ALIASES`, and nothing
    else. It deliberately does NOT drop words like "loop" or "trail": those
    separate "Terrace Pond North Loop" from "Terrace Pond North Trail", which
    are different walks, and a normaliser that collapsed them would report a
    confident wrong join rather than no join.
    """
    if not title:
        return ""
    # Apostrophes are DELETED rather than turned into a space, and the
    # distinction is not cosmetic: "Anthony's Nose" against "Anthonys Nose"
    # is a real pair in this corpus, and splitting on the apostrophe would
    # leave "anthony s nose" beside "anthonys nose" and refuse the join.
    words = _TITLE_NOISE_RE.sub(" ", _APOSTROPHE_RE.sub("", title.lower())).split()
    return " ".join(_TITLE_ALIASES.get(word, word) for word in words)


def photo_key(filename: str | None) -> str:
    """The join key between a write-up's image and a recovered photograph.

    Lowercased, and anything after a `?` dropped: Drupal's image derivatives
    arrive as `name.jpg?itok=...` and the same file is cited with and without
    that token on different captures of the same page. Two spellings of one
    file failing to join would look exactly like a photograph NYNJTC never
    published, which is the quiet failure this function exists to prevent.
    """
    if not filename:
        return ""
    return filename.split("?", 1)[0].strip().lower()


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


def metres_apart(page: Page, hike: Hike) -> float | None:
    """Great-circle metres between a write-up's coordinate and a hike's start,
    or None when either side has none.

    `lib.hikefinder.metres_between` rather than a second implementation, so
    this distance and the export's own distances are measured on one sphere.
    """
    here, there = page.where, (hike.lat, hike.lon)
    if here is None or hike.lat is None or hike.lon is None:
        return None
    return metres_between(here, there)


def hike_from_page(page: Page) -> Hike:
    """The write-up read as a hike, for a page the export does not contain.

    `hike_id` is empty, and that is the whole signal: a row carrying one names
    a walk NYNJTC published and the 385-hike export does not have, so there is
    nothing for a photograph to attach to and NOTHING SHIPS from it. It earns
    a sheet row anyway because a person reading the write-up's own title can
    often place it by hand, which is a far better row to be handed than
    "matched nothing".
    """
    return Hike(
        hike_id="",
        name=page.name,
        park=page.park or "",
        region=page.region or "",
        description=page.description,
        lat=page.lat,
        lon=page.lon,
    )


def resolve_page(page: Page, hikes: list[Hike]) -> tuple[Hike, str, float | None] | None:
    """Which export hike this archived write-up is, and how that was decided.

    Title first, distance only as a tie-break or a corroboration - the order
    the docstring sets out. `None` when the export has no hike this page can
    honestly be said to be.
    """
    wanted = normalise_title(page.name)
    if not wanted:
        return None

    same_title = [hike for hike in hikes if normalise_title(hike.name) == wanted]
    if same_title:
        # Two export hikes can share a title (a loop walked from either end),
        # and then the coordinate is what separates them. A page with no
        # coordinate takes the first, which is why the sheet still shows the
        # runners-up.
        same_title.sort(key=lambda h: metres_apart(page, h) if metres_apart(page, h) is not None else float("inf"))
        chosen = same_title[0]
        return chosen, BASIS_PAGE_NAME, metres_apart(page, chosen)

    # No title agreement in full. Distance NARROWS from here, and a candidate
    # with no title words in common is refused outright rather than ranked
    # low: a park holds dozens of these walks and several start from one car
    # park, so "nearest" is not an answer to "which".
    page_terms = distinctive_terms(page.name)
    if not page_terms:
        return None

    near: list[tuple[int, float, Hike]] = []
    for hike in hikes:
        gap = metres_apart(page, hike)
        if gap is None or gap > MAX_JOIN_METRES:
            continue
        shared = page_terms & hike.name_terms
        if not shared:
            continue
        near.append((len(shared), gap, hike))

    if not near:
        return None
    near.sort(key=lambda row: (-row[0], row[1]))
    _, gap, chosen = near[0]
    return chosen, BASIS_PAGE_NEAR, gap


def pages_by_photo(pages: list[Page]) -> dict[str, tuple[Page, PagePhoto]]:
    """Which write-up showed each photograph, and how that page credited it.

    A file cited by more than one write-up keeps the FIRST, and the collision
    is not silent - `main()` counts them, because a photograph NYNJTC reused
    across two walks is a row a person must decide rather than a tie a sort
    order should settle.

    THE CREDIT COMES BACK WITH THE PAGE (#1504) because there is nowhere else
    it can come from. The photograph cache knows only what the filename says;
    the page is where NYNJTC wrote the photographer's name, and the licence
    conditions publication on it.
    """
    found: dict[str, tuple[Page, PagePhoto]] = {}
    for page in pages:
        for photo in page.photos:
            found.setdefault(photo_key(photo.filename), (page, photo))
    return found


def best_pairings(photos: list[Photo], hikes: list[Hike], pages: list[Page] | None = None) -> dict[str, list[Pairing]]:
    """Every photograph's candidate hikes, best route first.

    Candidates are kept rather than only the winner, because the sheet's job
    is to let a person choose - and a photograph whose top two candidates are
    a point apart is exactly the row where the automatic answer is least
    trustworthy and a human is most useful. With the write-ups recovered there
    is a second reason: the text runners-up under a page-derived winner are
    how a reviewer sees the two routes disagreeing.

    `pages` is optional so this still runs, and still means what it meant,
    against a photograph recovery with no write-ups behind it.
    """
    showed = pages_by_photo(pages or [])
    placed: dict[str, tuple[Hike, str, float | None] | None] = {}

    ranked: dict[str, list[Pairing]] = {}
    for photo in photos:
        by_text = [p for p in (score_pair(photo, hike) for hike in hikes) if p is not None]
        by_text.sort(key=lambda p: -p.score)

        found_on = showed.get(photo_key(photo.filename))
        page, shown_as = found_on if found_on else (None, None)
        from_page: Pairing | None = None
        if page is not None:
            if page.url not in placed:
                placed[page.url] = resolve_page(page, hikes)
            resolved = placed[page.url]
            if resolved is None:
                from_page = Pairing(photo, hike_from_page(page), 0.0, basis=BASIS_PAGE_ONLY, page=page, shown_as=shown_as)
            else:
                hike, basis, gap = resolved
                # The text route's own verdict on the SAME hike, carried over
                # so the sheet can show what the words said about the pairing
                # the page already settled - including that they said nothing,
                # which is common and is not a problem.
                agreed = next((p for p in by_text if p.hike.hike_id == hike.hike_id), None)
                from_page = Pairing(
                    photo,
                    hike,
                    agreed.score if agreed else 0.0,
                    on_name=agreed.on_name if agreed else set(),
                    on_description=agreed.on_description if agreed else set(),
                    on_park=agreed.on_park if agreed else set(),
                    phrases=agreed.phrases if agreed else set(),
                    basis=basis,
                    page=page,
                    shown_as=shown_as,
                    metres=gap,
                )

        for candidate in by_text:
            candidate.shown_as = shown_as

        found = [from_page] if from_page else []
        found.extend(p for p in by_text if from_page is None or p.hike.hike_id != from_page.hike.hike_id)
        found.sort(key=lambda p: p.rank)
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


def page_photos_of(row: dict) -> list[PagePhoto]:
    """One cached page's photographs, from either shape of the cache.

    A cache written before #1504 holds bare filenames, and a string there
    means "nobody looked for a credit" rather than "there is none" - but the
    two have to resolve to the same thing here, because this module cannot
    tell them apart and the licence will not let it guess. So an old row
    yields `credit=None` and is refused by the gate, which is the correct
    answer for a photograph whose credit nobody has read.
    """
    found = []
    for photo in row.get("photos") or []:
        if isinstance(photo, str):
            found.append(PagePhoto(filename=photo, credit=None, credit_basis=None))
        elif isinstance(photo, dict) and photo.get("filename"):
            found.append(
                PagePhoto(
                    filename=photo["filename"],
                    credit=photo.get("credit"),
                    credit_basis=photo.get("credit_basis"),
                )
            )
    return found


def load_pages(path: Path | None = None) -> list[Page]:
    """The archived write-ups, or an empty list.

    EMPTY IS A LEGITIMATE ANSWER and not an error: the write-up recovery is a
    separate, slow leg that a photographs-only run has not done. `main()` says
    which case it is rather than letting "no page joins" read as "the join
    found nothing", because those look identical in a count and mean opposite
    things.
    """
    path = path or PAGES_PATH
    if not path.exists():
        return []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    pages = []
    for row in document.get("pages", []):
        try:
            pages.append(
                Page(
                    url=row["url"],
                    timestamp=row.get("timestamp", ""),
                    name=row.get("name") or "",
                    park=row.get("park"),
                    region=row.get("region"),
                    lat=row.get("lat"),
                    lon=row.get("lon"),
                    description=row.get("description") or "",
                    photos=page_photos_of(row),
                )
            )
        except (TypeError, KeyError):
            continue
    return pages


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


def above_the_fold(pairing: Pairing, minimum: float) -> bool:
    """Whether this row is one the sheet leads with.

    A row PLACED by a write-up qualifies WHATEVER its text score, and that is
    the reorder in one line: NYNJTC printed the photograph on the hike's own
    page, so a low text score underneath it says the filename and the prose
    share few words, which is a fact about wording and not about the pairing.

    A page-only row does not qualify. It is certain about a write-up and empty
    about the export, and leading with it would be leading with work that
    cannot end in a photograph.

    NEITHER DOES AN UNCREDITED ONE, whatever route reached it (#1504). The
    credit is the licence's condition, so a row without one cannot end in a
    published photograph either - the difference is that a page-only row is
    missing a HIKE and this one is missing PERMISSION, and only the second of
    those can be fixed by a person reading the sheet. It stays visible below
    the line for the reason every other refused row does: a count of what was
    withheld is a fact about this corpus worth seeing.
    """
    return pairing.publishable and (pairing.placed_by_page or pairing.score >= minimum)


def disagrees(candidates: list[Pairing], minimum: float) -> bool:
    """A page-derived winner with a text candidate pointing somewhere else.

    Surfaced rather than resolved. Either the text matcher is wrong in a way
    worth seeing, or a write-up reused a photograph from another walk, and
    both are a person's call.
    """
    if not candidates or not candidates[0].placed_by_page:
        return False
    top = candidates[0]
    return any(c.hike.hike_id != top.hike.hike_id and c.score >= minimum for c in candidates[1:])


def _reasons(pairing: Pairing) -> str:
    parts = []
    if pairing.page is not None:
        shown = f"shown on \u201c{pairing.page.name}\u201d"
        if pairing.metres is not None:
            shown += f", {pairing.metres:,.0f} m from the start"
        elif pairing.basis != BASIS_PAGE_ONLY:
            shown += ", no coordinate on either side"
        parts.append(shown)
    if pairing.phrases:
        parts.append("phrase: " + ", ".join(sorted(pairing.phrases)))
    if pairing.on_name:
        parts.append("name: " + ", ".join(sorted(pairing.on_name)))
    if pairing.on_description:
        parts.append("description: " + ", ".join(sorted(pairing.on_description)))
    if pairing.on_park:
        parts.append("park: " + ", ".join(sorted(pairing.on_park)))
    if pairing.basis == BASIS_PAGE_ONLY:
        parts.append("the export has no hike by this title - place it by hand or leave it")
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
    strong = weak = unmatched = joined = clashes = uncredited = 0

    def order(item: tuple[str, list[Pairing]]) -> tuple[int, int, float]:
        _, candidates = item
        if not candidates:
            return (2, len(BASIS_ORDER), 0.0)
        clash = 0 if disagrees(candidates, minimum) else 1
        return (clash, *candidates[0].rank)

    for digest, candidates in sorted(ranked.items(), key=order):
        photo = by_digest[digest]
        if not candidates:
            unmatched += 1
            continue
        top = candidates[0]
        clash = disagrees(candidates, minimum)
        if clash:
            clashes += 1
        if top.placed_by_page:
            joined += 1
        if above_the_fold(top, minimum):
            strong += 1
        else:
            weak += 1
        alternatives = "".join(
            f"<li>{html.escape(c.hike.name)} <span class=s>{c.score:.2f}</span> "
            f"<span class=basis>{html.escape(c.basis)}</span> "
            f"<span class=w>{html.escape(_reasons(c))}</span></li>"
            for c in candidates[1:]
        )
        if top.publishable:
            credit_class = "credit"
            credit_line = f"Photo: {html.escape(top.credit)} ({html.escape(top.credit_basis or '')})"
        else:
            uncredited += 1
            credit_class = "warn"
            credit_line = "no credit &mdash; outside the permission, cannot ship"
        classes = " ".join(
            part
            for part in (
                ("strong" if above_the_fold(top, minimum) else "weak"),
                ("clash" if clash else ""),
                ("" if top.publishable else "uncredited"),
            )
            if part
        )
        unplaced = ' <span class="warn">not in the export</span>' if not top.hike.hike_id else ""
        rows.append(
            f"""<tr class="{classes}">
  <td><img src="../raw/{ARCHIVE_STORE_DIRNAME}/{html.escape(digest)}.jpg" alt=""
           title="{html.escape(photo.filename)}"></td>
  <td><div class=subj>{html.escape(photo.subject)}</div>
      <div class=w>{html.escape(photo.filename)}</div>
      <div class=w>{photo.width}&times;{photo.height} &middot; {html.escape(photo.frame)} frame</div>
      <div class="{credit_class}">{credit_line}</div></td>
  <td><div class=hike>{html.escape(top.hike.name)}{unplaced}</div>
      <div class=w>{html.escape(top.hike.park)} &middot; {html.escape(top.hike.region)}</div>
      <div class=score><span class=basis>{html.escape(top.basis)}</span> &middot; text {top.score:.2f}</div>
      {'<div class="warn">the page and the words point at different hikes</div>' if clash else ""}
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
 .clash{{background:#fdf2f8}} .clash td{{border-top:2px solid #be185d}}
 .warn{{color:#9d174d;font-size:12px;font-weight:600}}
 .credit{{color:#14532d;font-size:12px}}
 .uncredited{{opacity:.55}} .uncredited .subj,.uncredited .hike{{text-decoration:line-through}}
 .basis{{background:#e8f0e8;border-radius:4px;padding:1px 6px;font-size:12px;color:#14532d}}
 .note{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:14px;margin-bottom:18px}}
</style>
<h1>NYNJTC archive photographs, matched to hikes</h1>
<div class=note>
<p><strong>{joined}</strong> photographs were read off the write-up that published them;
<strong>{strong}</strong> rows lead the sheet; <strong>{weak}</strong> fall below that line;
<strong>{unmatched}</strong> match nothing at all.</p>
<p><strong>A row leads the sheet when it is credited AND either joined or scored at or above
{minimum:.2f}.</strong> The credit is first because it is the only one of those that no
amount of reviewing can supply &mdash; a joined row used to lead on the join alone, and on
this corpus that printed a lead count beside hundreds of struck-through joined rows.</p>
<p><strong>Read the basis before the number.</strong> <span class=basis>page + title</span>
means NYNJTC printed this photograph on that hike's own page and both call the walk the same
thing &mdash; that is a fact recovered from the archive, not a string match, and the
<em>text</em> figure beside it only says how many words the filename and the write-up happen
to share. <span class=basis>subject text</span> is the older route and the weaker one: the
words alone, with no page behind them.</p>
<p><strong>The text score is a rank, not a probability.</strong> It has not been calibrated
against any confirmed set, because there is no confirmed set until this sheet is worked.
Nothing here ships until a row is confirmed into <code>reference/nynjtc_hike_photos.json</code>
by hand &mdash; a photograph that passes every automatic bar can still be of the wrong place,
which is exactly what the Asiatic dayflower on Gravel Springs Hut Shelter was.</p>
<p><strong>{uncredited}</strong> rows are struck through, and they are not a matching
problem. <code>sources.json</code>&rsquo;s <code>nynjtc_hikes_licence</code> makes attribution
&ldquo;a condition rather than a courtesy &hellip; a photograph the page does not credit is
not fetched at all&rdquo;, and the recovery that produced these selected by DIRECTORY PREFIX
&mdash; <code>u26</code> is a site-wide upload folder, wider than the hikes the permission
covers. So a row with no photographer&rsquo;s name is outside the permission whether or not
the hike beside it is right, and no amount of reviewing can put it inside. Confirming one
would publish somebody&rsquo;s photograph without their credit; the sheet will not offer it
and the proposed file does not carry it. They are shown so the SIZE of that gap is visible
rather than quietly subtracted &mdash; see
<a href="https://github.com/OurHike/OurHike/issues/1504">#1504</a>.</p>
<p>A credit reading <code>(filename)</code> rests on NYNJTC having written the
photographer&rsquo;s name into the file name rather than into the page text. That is this
build&rsquo;s reading of the condition and not the licence&rsquo;s own words &mdash; if you
read it more strictly, refuse those rows.</p>
<p><strong>{clashes}</strong> rows are outlined: the page says one hike and the words prefer
another. They are first on purpose. Shaded rows fall below the line and are shown anyway,
because a low score on a correct pairing is a fact about this matcher and not about the
photograph.</p>
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

    pages = load_pages()
    # Said before the counts, because "0 joined" means one thing when there
    # are no write-ups and the opposite when there are 385 of them.
    if pages:
        showed = pages_by_photo(pages)
        print(f"{len(pages)} archived write-ups, citing {len(showed)} distinct photographs.")
    else:
        print(f"No write-ups at {PAGES_PATH.name} - run fetch_wayback_hike_pages.py to get the")
        print("photograph -> hike join NYNJTC itself published. Falling back to subject text,")
        print("which is the weakest of the four routes and the only one available without it.")

    print(f"{len(photos)} photographs against {len(hikes)} hikes ...")
    ranked = best_pairings(photos, hikes, pages)

    tops = [c[0] for c in ranked.values() if c]
    strong = [p for p in tops if above_the_fold(p, minimum)]
    # THE LICENCE GATE, applied where the file is written rather than where
    # the rows are scored (#1504): every one of these is still counted, shown
    # and explained, and none of them reaches the proposed file.
    withheld = [p for p in tops if not p.publishable]
    unmatched = sum(1 for c in ranked.values() if not c)
    by_basis = {basis: sum(1 for p in tops if p.basis == basis) for basis in BASIS_ORDER}
    clashing = sum(1 for c in ranked.values() if disagrees(c, minimum))

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    PROPOSED_PATH.write_text(
        json.dumps(
            {
                "min_score": minimum,
                "note": "Proposed, not confirmed. reference/nynjtc_hike_photos.json is the confirmed join.",
                "licence": (
                    "sources.json nynjtc_hikes_licence makes the photographer's credit a "
                    "condition of the permission, so a photograph nothing credits is not "
                    "here - however good its pairing. See #1504."
                ),
                "basis_order": list(BASIS_ORDER),
                "write_ups": len(pages),
                "withheld_uncredited": len(withheld),
                "matches": [
                    {
                        "digest": p.photo.digest,
                        "hike_id": p.hike.hike_id,
                        "hike_name": p.hike.name,
                        # HOW this was reached, carried beside the number so a
                        # row read out of this file cannot lose the difference
                        # between a page join and a string comparison.
                        "basis": p.basis,
                        "score": round(p.score, 3),
                        "metres_from_start": round(p.metres) if p.metres is not None else None,
                        "page_title": p.page.name if p.page else None,
                        "page_url": p.page.url if p.page else None,
                        "subject": p.photo.subject,
                        "credit": p.credit,
                        # WHERE the credit was read, carried beside it for the
                        # same reason `basis` is: a row copied out of this file
                        # must not lose the difference between NYNJTC naming
                        # the photographer in their prose and this build
                        # reading a name out of a file name.
                        "credit_basis": p.credit_basis,
                        "frame": p.photo.frame,
                        "reasons": _reasons(p),
                    }
                    for p in sorted([p for p in tops if p.publishable], key=lambda p: p.rank)
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_sheet(ranked, photos, minimum, SHEET_PATH)

    print()
    for basis in BASIS_ORDER:
        print(f"  {basis:<22}  {by_basis[basis]}")
    print(f"  {'nothing at all':<22}  {unmatched}")
    print()
    print(f"  leading the sheet       {len(strong)}")
    print(f"  below the line          {len(tops) - len(strong)}")
    print(f"  no credit, cannot ship  {len(withheld)}  <- the licence, not the matcher (#1504)")
    if clashing:
        print(f"  page vs words disagree  {clashing}  <- read these first")
    # Only a row with an export hike behind it can ever ship: a page-only row
    # names a walk NYNJTC published and this export does not have.
    hikes_covered = len({p.hike.hike_id for p in strong if p.hike.hike_id})
    print(f"  distinct hikes reached  {hikes_covered} of {len(hikes)}")
    print()
    print(f"  sheet     {SHEET_PATH}")
    print(f"  proposed  {PROPOSED_PATH}")
    print()
    print("  NOTHING SHIPS FROM THIS FILE. A confirmed row lives in")
    print(f"  {REFERENCE_PATH.relative_to(ROOT)}, written by a person working the sheet.")
    if withheld and len(withheld) == len(tops):
        print()
        print("  NOT ONE matched photograph carries a credit. Before reading that as a fact")
        print("  about the corpus, check that the write-ups were recovered by a build that")
        print("  looks for one: a cache written before #1504 holds bare filenames, and this")
        print("  refuses those by design. fetch_wayback_hike_pages.py --probe settles it.")
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--min",
        dest="minimum",
        type=float,
        default=DEFAULT_MIN_SCORE,
        help=(
            "Where the fold sits among text-scored rows. Rows placed by an "
            "archived write-up lead the sheet regardless. Ranks; decides nothing."
        ),
    )
    args = parser.parse_args(argv)
    return main(args.minimum)


if __name__ == "__main__":
    raise SystemExit(run())
