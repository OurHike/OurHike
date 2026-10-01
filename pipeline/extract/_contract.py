"""The extract contract: what a club folder holds, and how a run finds what is in it.

pipeline/ELT.md, "The folder contract", is the design this implements (#1793 —
Rebuild the data platform as dlt → dbt: seven contracted marts, a monthly
refresh, published docs, and lighter phone downloads). One folder per managing
organisation in reference/trail_orgs.json, named by its slug with `-` written
`_`, and exactly the eleven files in TYPES. Each file is one of these:

    CLAIMS + RESOURCES   the keys it owns (sources.json keys, or a reviewed
                         pipeline/reference/ path), and a Resource for each
    SHARES = "<type>"    a sibling type file whose resource also feeds this
                         type; it claims nothing, so a key is still claimed once
    NOT_AVAILABLE        a dated NotAvailable: nothing this pipeline may load
                         for the type, as of the day a person looked
    SAME_AS              dated SameAs notes for republished copies of a dataset
                         another resource extracts; alone, or beside CLAIMS

A builder takes a key, never a URL (extract/_kinds.py), so a club file cannot
fetch an upstream sources.json does not register - CONTRIBUTING.md's "establish
its licence first and record it", enforced by construction.

`discover()` reads the files; tests/test_extract_layout.py holds the shape;
extract/_run.py runs what they declare.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from types import ModuleType

from lib.freshness_state import Freshness

EXTRACT_DIR = Path(__file__).parent
PIPELINE_DIR = EXTRACT_DIR.parent

TYPES = (
    "org",
    "trail_lines",
    "points_of_interest",
    "elevation",
    "closures",
    "warnings",
    "places",
    "suggested_hikes",
    "podcasts",
    "challenges",
    "photos",
)

CADENCES = ("hourly", "daily", "weekly", "monthly")

# Decision 28a: the lane belongs to the type. Closures and warnings are the
# two safety types a hiker reads as "now", so they ride the hourly lane;
# everything else a club publishes is monthly. A resource that differs says
# why on itself (Resource.cadence_reason), and the layout test refuses an
# override without one.
DEFAULT_CADENCE = "monthly"
CADENCE_BY_TYPE = {"closures": "hourly", "warnings": "hourly"}

# Types whose honest row count can be zero: every closure lifted is exactly
# what an empty closures table looks like. A layer outside these types may
# still be empty when its sources.json entry says `may_be_empty: true`. An
# allowed zero still needs the upstream's own count read in the same run
# (extract/_run.py's run check), because an empty answer from a failed fetch
# looks the same as a quiet trail.
MAY_BE_EMPTY = frozenset({"closures", "warnings"})

# @unvalidated: the age at which a "not available" note must be looked at
# again. 180 days is a round number, not a measurement; what would settle it
# is how often the next re-survey after ORG_COVERAGE_SURVEY.md overturns a
# note of a given age. A stale note fails the monthly note-ageing job, never a
# pull request (ELT.md, "The data checks", check 3).
RECHECK_AFTER_DAYS = 180

# Not a club: national services, aggregators and OurHike's own data (ELT.md,
# "_shared/"). Free-form, and outside the eleven-file rule.
SHARED_FOLDER = "_shared"

# trail_orgs.json types that get no club folder (decision 18): umbrellas,
# route-only trails and aggregators publish through somebody else, so each
# gets one dated line in _shared/not_clubs.py instead. Every other row is a
# managing organisation, and its folder is the eleven files.
NOT_CLUB_TYPES = frozenset({"national_umbrella", "route_only", "aggregator"})


def folder_for_slug(slug: str) -> str:
    """The folder a trail_orgs.json slug lives in: `-` written `_`.

    Python cannot import a hyphen. None of the 173 slugs holds an underscore
    (measured 2026-10-01, ELT.md), so the mapping reverses exactly, which
    slug_for_folder relies on and the layout test checks.
    """
    return slug.replace("-", "_")


def slug_for_folder(folder: str) -> str:
    return folder.replace("_", "-")


def raw_table(folder: str, key: str) -> str:
    """`raw_<folder>__<key>`, the raw table a club's resource lands in.

    Written as dlt's `table_name` and never passed through dlt's own
    normalizer: `normalize_table_identifier()` alone collapses the `__` to one
    underscore, while a run keeps the name as written (measured 2026-10-01,
    dlt 1.30.0, ELT.md "Folder name = trail_orgs.json slug"). A key that is a
    reference/ path is written as its path under reference/, without `.json`:
    `reference/challenges/atc` lands as `raw_atc__challenges_atc`.
    """
    if key.startswith("reference/"):
        key = key.removeprefix("reference/").removesuffix(".json").replace("/", "_")
    return f"raw_{folder}__{key.replace('-', '_')}"


@dataclass(frozen=True)
class NotAvailable:
    """Nothing this pipeline may load from this org for this type, as of `confirmed`.

    Three cases share the shape: not published; published but refused, with
    the refusing words quoted in `terms`; or published and not landed yet,
    with `reason` saying what landing it waits on (usually a sources.json row,
    since a builder takes a registered key). `checked` lists what a person
    looked at, written so the next person can repeat it, and `where` the URLs.

    A note says what was checked, never that a search happened that did not.
    The layout test can check a note's shape and nothing else - it cannot tell
    a search that was done from one that was written down - so that half is a
    reviewer's check (ELT.md, "A GIS-shaped type is not given up early").
    """

    confirmed: date
    checked: tuple[str, ...]
    where: tuple[str, ...]
    recheck_after_days: int = RECHECK_AFTER_DAYS
    terms: str | None = None
    reason: str | None = None

    def problems(self, today: date) -> list[str]:
        """Why this note is not a well-formed note, or [] when it is."""
        problems = []
        if self.confirmed > today:
            problems.append(f"confirmed {self.confirmed} is in the future")
        if not self.checked or not all(isinstance(item, str) and item.strip() for item in self.checked):
            problems.append("checked must list what was looked at")
        if not self.where or not all(isinstance(url, str) and url.startswith("https://") for url in self.where):
            problems.append("where must list https URLs")
        if self.recheck_after_days <= 0:
            problems.append("recheck_after_days must be positive")
        return problems

    def overdue(self, today: date) -> bool:
        """True once the note is past its recheck date: news for the monthly job, not a pull request failure."""
        return (today - self.confirmed).days > self.recheck_after_days


@dataclass(frozen=True)
class SameAs:
    """A republished copy of a dataset another resource already extracts: noted, never loaded.

    Each upstream dataset is extracted once, in its steward's folder (decision
    34; the maintainer: "Are we landing the same data, multiple times? We
    shouldn't."). A copy - an ArcGIS Online twin of an on-prem layer, an older
    export of the same assets - is recorded here so the next person does not
    add it as a second resource and leave dedup to remove it. It ages like a
    NotAvailable, because a copy can stop being one: once its publisher edits
    it apart from the original, it is an independent dataset and gets a
    resource of its own.
    """

    original: str  # the claimed key whose resource extracts the dataset
    copy: tuple[str, ...]  # the copy's URLs or ArcGIS item ids
    confirmed: date
    checked: tuple[str, ...]  # what shows it is the same data
    recheck_after_days: int = RECHECK_AFTER_DAYS

    def problems(self, today: date) -> list[str]:
        problems = []
        if self.confirmed > today:
            problems.append(f"confirmed {self.confirmed} is in the future")
        if not self.copy or not self.checked:
            problems.append("a SAME_AS note names the copy and what shows it is the same data")
        if self.recheck_after_days <= 0:
            problems.append("recheck_after_days must be positive")
        return problems


@dataclass(frozen=True)
class Resource:
    """One upstream, landing as one raw table. Subclassed per source kind in extract/_kinds.py.

    `club` and `type` are filled in by discover() from where the file sits, so
    a club file writes only the key: the table name, the cadence and the lane
    all follow from the folder and the type, and cannot disagree with them.
    """

    key: str
    club: str | None = None
    type: str | None = None
    cadence_override: str | None = None
    cadence_reason: str | None = None

    @property
    def table(self) -> str:
        if self.club is None:
            raise ValueError(f"{self.key}: table asked for before discover() placed the resource")
        return raw_table(self.club, self.key)

    @property
    def name(self) -> str:
        """The dlt resource name, which is also where its marker lives in dlt state: the table, unless shared."""
        return self.table

    @property
    def schema_contract(self) -> dict | None:
        """dlt's schema contract for the table, or None for dlt's default."""
        return None

    @property
    def cadence(self) -> str:
        if self.cadence_override is not None:
            return self.cadence_override
        return CADENCE_BY_TYPE.get(self.type or "", DEFAULT_CADENCE)

    @property
    def may_be_empty(self) -> bool:
        return self.type in MAY_BE_EMPTY

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """Our code, before dlt: (verdict, the upstream marker it compared).

        FRESH leaves the resource out of the run, and only FRESH does: STALE
        and UNKNOWN both fetch, and a check that errors is UNKNOWN
        (lib/freshness_state.py: "THE FAILURE THAT MATTERS is a false
        'fresh'"). The base answers STALE, which costs a read and nothing else.
        """
        return Freshness.STALE, None

    def rows(self, proofs: dict[str, int]):
        """Yield the upstream's rows, recording the upstream's own count in `proofs[self.table]` where it has one."""
        raise NotImplementedError

    def column_hints(self) -> dict:
        """dlt column hints for this table. Asked for only when the resource runs."""
        return {}


@dataclass
class ClubFile:
    """One of a club folder's eleven files, as discover() read it."""

    club: str
    type: str
    path: Path
    claims: tuple[str, ...] = ()
    resources: tuple[Resource, ...] = ()
    shares: str | None = None
    note: NotAvailable | None = None
    same_as: tuple[SameAs, ...] = ()

    @property
    def form(self) -> str:
        """Which shape the file takes, or "invalid" when it takes none or several.

        SAME_AS notes may stand alone, when a copy is all the org publishes for
        the type, or ride a claiming file, for the copies it does not extract.
        """
        forms = [
            name
            for name, present in (
                ("claims", bool(self.claims) or bool(self.resources)),
                ("shares", self.shares is not None),
                ("note", self.note is not None),
            )
            if present
        ]
        if not forms and self.same_as:
            return "same_as"
        if len(forms) != 1 or (self.same_as and forms[0] != "claims"):
            return "invalid"
        return forms[0]


def club_folders(root: Path = EXTRACT_DIR) -> list[Path]:
    """Every club folder under `root`: a directory not starting with `_` or `.`."""
    return sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")))


def _load_module(path: Path, club: str) -> ModuleType:
    """Import one club file by path. Club folders hold no __init__.py on purpose, so the eleven-file count is exact."""
    spec = importlib.util.spec_from_file_location(f"extract.{club}.{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_club_file(path: Path) -> ClubFile:
    club, type_ = path.parent.name, path.stem
    module = _load_module(path, club)
    resources = tuple(replace(resource, club=club, type=type_) for resource in getattr(module, "RESOURCES", ()) or ())
    return ClubFile(
        club=club,
        type=type_,
        path=path,
        claims=tuple(getattr(module, "CLAIMS", ()) or ()),
        resources=resources,
        shares=getattr(module, "SHARES", None),
        note=getattr(module, "NOT_AVAILABLE", None),
        same_as=tuple(getattr(module, "SAME_AS", ()) or ()),
    )


def discover(root: Path = EXTRACT_DIR) -> list[ClubFile]:
    """Every type file in every club folder under `root`, in a stable order."""
    files = []
    for folder in club_folders(root):
        for path in sorted(folder.glob("*.py")):
            files.append(read_club_file(path))
    return files


def all_resources(files: list[ClubFile]) -> list[Resource]:
    """Every Resource the club files declare. A SHARES file adds none: its sibling's resource is the one row."""
    return [resource for club_file in files for resource in club_file.resources]
