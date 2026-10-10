"""The extract contract: what a club answers for each type, and how a run finds it.

pipeline/ELT.md, "The folder contract", is the design this implements (#1793 —
Rebuild the data platform as dlt → dbt: seven contracted marts, a monthly
refresh, published docs, and lighter phone downloads), as decision 88 amends
it. Every managing organisation in reference/trail_orgs.json answers each of
the ten FILE_TYPES exactly once, in one of two homes:

    a resource file      extract/<folder>/<type>.py, the folder named by the
                         club's slug with `-` written `_`: CLAIMS + RESOURCES,
                         the keys it owns (sources.json keys, or a reviewed
                         pipeline/reference/ path) and a Resource for each;
                         it may carry SAME_AS for copies it does not extract,
                         or be SAME_AS alone, when a copy is all the org
                         publishes for the type
    a row of             extract/not_available.toml, [<folder>.<type>]: a
    not_available.toml   dated note (a NotAvailable: nothing this pipeline may
                         load for the type, as of the day a person looked), or
                         a share (`shares = "<type>"`: a sibling type whose
                         resource file also feeds this type, so a key is still
                         claimed once)

and the eleventh type, `org`, with the catalogue row discover() makes for every
managing club. So a club folder holds only its resource files, and a club with
none has no folder.

A builder takes a key, never a URL (extract/_kinds.py), so a club file cannot
fetch an upstream sources.json does not register - CONTRIBUTING.md's "establish
its licence first and record it", enforced by construction.

`discover()` reads the files and the rows; tests/test_extract_layout.py holds
the shape; extract/_run.py runs what they declare.
"""

from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from types import ModuleType

import tomllib

from lib.freshness_state import Freshness

EXTRACT_DIR = Path(__file__).parent
PIPELINE_DIR = EXTRACT_DIR.parent
TRAIL_ORGS_PATH = PIPELINE_DIR / "reference" / "trail_orgs.json"

# Every managing club's notes and shares, one row per club and type (decision
# 88): the 1,095 NOT_AVAILABLE note files and 44 SHARES files it replaced, at
# bcc70dd0. Its header comment is the format.
NOT_AVAILABLE_FILE = "not_available.toml"

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

# The ten types a managing club answers, each with a resource file in its
# folder or a row of not_available.toml. `org` is not among them: discover()
# makes every managing club's catalogue row from trail_orgs.json (decision 88).
FILE_TYPES = tuple(type_ for type_ in TYPES if type_ != "org")

CADENCES = ("hourly", "daily", "weekly", "monthly")

# The lane belongs to the type (ELT.md decision 28a). Closures and warnings
# are the two safety types a hiker reads as "now", so they ride the hourly
# lane; everything else a club publishes is monthly. A resource that differs
# says why on itself (Resource.cadence_reason), and the layout test refuses an
# override without one.
DEFAULT_CADENCE = "monthly"
CADENCE_BY_TYPE = {"closures": "hourly", "warnings": "hourly"}

# Types whose honest row count can be zero: every closure lifted is exactly
# what an empty closures table looks like. A layer outside these types may
# still be empty when its sources.json entry says `may_be_empty: true`. An
# allowed zero still needs the upstream's own count read in the same run
# (extract/_run.py's run check), because an empty answer from a failed fetch
# looks the same as a quiet trail; Resource.zero_proof says which kinds read
# such a count.
MAY_BE_EMPTY = frozenset({"closures", "warnings"})

# @unvalidated: the age at which a "not available" note must be looked at
# again. 180 days is a round number, not a measurement; what would settle it
# is how often the next re-survey after ORG_COVERAGE_SURVEY.md overturns a
# note of a given age. A stale note fails the monthly note-ageing job, never a
# pull request (ELT.md, "The data checks", check 3).
RECHECK_AFTER_DAYS = 180

# Not a club: national services, aggregators and OurHike's own data (ELT.md,
# "_shared/"). Free-form, and outside the rule that a club answers each type once.
SHARED_FOLDER = "_shared"

# trail_orgs.json types that are not managing clubs (decision 18): umbrellas,
# route-only trails and aggregators publish through somebody else, so each
# gets one dated line in _shared/not_clubs.py instead. Every other row is a
# managing organisation, which answers every type: a resource file in its
# folder, or a row of not_available.toml, and a catalogue row.
NOT_CLUB_TYPES = frozenset({"national_umbrella", "route_only", "aggregator"})

# The fields a row of not_available.toml may carry, by its kind. Anything else
# is refused where the row is read, because a misspelt `terms` would otherwise
# drop a refusal's quoted words without a sound.
NOTE_FIELDS = frozenset({"confirmed", "recheck_after_days", "summary", "checked", "where", "terms", "reason"})
SHARE_FIELDS = frozenset({"shares", "summary"})


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

    Passed to dlt as `table_name`, which a run keeps as written, though
    `normalize_table_identifier()` called alone would collapse the `__` to one
    underscore (measured 2026-10-01, dlt 1.30.0, ELT.md "Folder name =
    trail_orgs.json slug"). A file-path key loses `.json` and `reference/`:
    `reference/challenges/atc` lands as `raw_atc__challenges_atc`, and the
    registry's own `sources.json` as `raw_registry__sources`.
    """
    key = key.removeprefix("reference/").removesuffix(".json").replace("/", "_")
    # dlt escapes a `__`-separated segment that starts with a digit with a
    # leading underscore: `raw_usgs__3dep_13_current` landed as
    # `raw_usgs___3dep_13_current`, and every check reading the name as
    # written found nothing (measured 2026-10-02, dlt 1.30.0).
    # tests/test_extract_layout.py holds every table to dlt's normalize_path.
    if key[:1].isdigit():
        raise ValueError(f"{folder}/{key}: a raw table's key may not start with a digit; dlt would rename the table")
    return f"raw_{folder}__{key.replace('-', '_')}"


@dataclass(frozen=True)
class NotAvailable:
    """Nothing this pipeline may load from this org for this type, as of `confirmed`.

    Three cases share the shape: not published; published but refused, the
    refusing words quoted in `terms`; or published and not landed yet,
    `reason` saying what landing waits on (usually a sources.json row, since a
    builder takes a registered key). `checked` lists what a person looked at,
    so the next person can repeat it, and `where` the URLs.

    A note says what was checked, never that a search happened that did not.
    The layout test checks a note's shape only, so whether the search was done
    is a reviewer's check (ELT.md, "A GIS-shaped type is not given up early").
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
class NotClub:
    """Why a trail_orgs.json row has no club folder: one dated line in _shared/not_clubs.py (decision 18).

    An umbrella or a route-only trail publishes through somebody else, so it
    has nothing of its own to extract. `why` is the reason in this file's own
    words; `terms` quotes a refusal verbatim where the row carries one (RTC's,
    ELT.md "Decision 18 overrides round 5 for two refusals").
    """

    type: str
    confirmed: date
    why: str
    terms: str | None = None


@dataclass(frozen=True)
class SameAs:
    """A republished copy of a dataset another resource already extracts: noted, never loaded.

    Each upstream dataset is extracted once, in its steward's folder (ELT.md
    decision 34; the maintainer: "Are we landing the same data, multiple
    times? We shouldn't."). A copy, such as an ArcGIS Online twin of an
    on-prem layer, is recorded here so nobody adds it as a second resource. It
    ages like a NotAvailable: once its publisher edits it apart from the
    original, it is an independent dataset and gets a resource of its own.
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


class Unavailable(Exception):
    """A change check's answer that the upstream cannot be read here, and that its own rule leaves out of the lane.

    Not a fourth Freshness: FRESH says "checked, nothing changed" and keeps
    the last rows; this says nobody can tell. extract/_run.py leaves the
    resource out and logs it `unavailable`, and extract/_warehouse.py
    withdraws the table rather than serve its last rows as current: absent
    means unknown, never zero (CLAUDE.md). Two raise it today:
    ConditionsQuery.change_check (extract/_kinds.py), for a table
    export_conditions.py's PENDING_READER_SETUP lists: notes and disputes are
    omitted while `field_notes` is not readable, and closures and reports
    carry on; and the NPS readers' change checks (extract/_json_apis.py),
    while NPS_API_KEY is unset. Any other failure raises as itself and stops
    the lane.
    """


@dataclass(frozen=True)
class Carried:
    """What extract/_run.py hands a resource that reads only what moved (Resource.carries), before its read.

    `committed` is the resource's table as its last committed load left it,
    dlt's own columns dropped (extract/_run.py's committed_rows()); empty on a
    first run. `progress` is what an earlier read that ran out of budget kept
    (Incomplete below), never landed. `seconds` is the read's budget from the
    moment it is handed this, or None for none, in which case the read reads
    everything it needs and never answers Incomplete.
    """

    committed: tuple[dict, ...] = ()
    progress: tuple[dict, ...] = ()
    seconds: float | None = None


class Incomplete(Exception):
    """A carrying resource's read that ran out of budget before it had every row its table must hold.

    Nothing lands: the table keeps its last committed rows, or on a first run
    stays not yet loaded, because a partial set landed under `replace` would
    read as the whole and drop every row not reached yet. `progress` is every
    row read so far, which extract/_run.py keeps in `_extract_progress` for a
    later read to carry until the table loads. `read` and `needed` are how
    many rows this run read and how many it still lacks, for the summary.
    """

    def __init__(self, message: str, progress: list[dict], read: int, needed: int):
        super().__init__(message)
        self.progress, self.read, self.needed = progress, read, needed


@dataclass(frozen=True)
class Resource:
    """One upstream, landing as one raw table. Subclassed per source kind in extract/_kinds.py.

    `club` and `type` are filled in by discover() from where the file sits (or,
    for a catalogue row, from the club it is made for), so a club file writes
    only the key: the table name, the cadence and the lane all follow from the
    folder and the type, and cannot disagree with them.
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
    def part(self) -> str:
        """Which part of its key's upstream this resource reads, when one key feeds two: "" for the whole of it.

        NYNJTC's Trail Alerts is the case: one registry row, read as its posts
        (hourly) and as the site's taxonomy terms (daily), two resources and two
        tables. The layout test's one-extraction rule tells them apart by this.
        """
        return ""

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

    @property
    def carries(self) -> bool:
        """Whether a run reads this through rows_carried(): only what moved, the rest carried from the last load.

        Such a resource still lands its whole table every run, under `replace`,
        so the run check, a refused load and a skipped resource behave as for
        any other; only the read is smaller. ATC's trail-updates pages are the
        one (extract/_kinds.py's AtcTrailUpdatePages).
        """
        return False

    @property
    def exact_proof(self) -> bool:
        """Whether the upstream's own count is exactly the rows the table must hold, so more rows refuse too.

        False for a count read beside the rows, such as ArcGIS's
        `returnCountOnly`, where a feature added between the count and the
        last page is not an error. True where the rows are built from the
        same answer the count is read from, so a difference either way is
        this code's mistake.
        """
        return False

    @property
    def zero_proof(self) -> str | None:
        """The upstream's own count this kind reads, in words, or None where the count it records is its own.

        A table that may be empty (MAY_BE_EMPTY, or a sources.json row's
        `may_be_empty`) may land zero rows only beside the upstream's own
        count, read in the same run, saying zero (pipeline/ELT.md, "A full
        reload that cannot empty a safety table"). A count is the upstream's
        when the upstream states it (ArcGIS's `returnCountOnly`, WordPress's
        `X-WP-Total`) or when it is the length of a whole answer in a fixed
        format that the reader refuses in any other shape (NWS's
        FeatureCollection, an RSS channel). A count this code makes of what it
        parsed out of a page written for people is not: a page whose layout
        moved parses to none exactly as a page with nothing on it does.

        extract/_run.py's run_check() refuses a zero from a kind whose answer
        here is None, whatever `proofs` holds, and keeps the shrink floor on
        such a table where it may be empty, since its shrink is no better
        proven than its zero. None is the default, so a kind nobody has
        checked is refused rather than trusted; each kind that reads a real
        count declares it on its own class, and
        tests/test_extract_zero_proofs.py pins which kinds do.
        """
        return None

    def rows(self, proofs: dict[str, int]):
        """Yield the upstream's rows, recording the upstream's own count in `proofs[self.table]` where it has one."""
        raise NotImplementedError

    def rows_carried(self, proofs: dict[str, int], carried: Carried):
        """rows(), for a resource that `carries`: read only what moved since `carried`, and yield the whole table.

        Raises Incomplete, landing nothing, when `carried.seconds` ran out
        before every row the table must hold had been read.
        """
        raise NotImplementedError

    def column_hints(self) -> dict:
        """dlt column hints for this table. Asked for only when the resource runs."""
        return {}


@dataclass
class ClubFile:
    """One club's answer for one type, as discover() read it.

    Three homes give one: a resource file in the club's folder (`path` is the
    file); a row of not_available.toml, a note or a share (`path` is that file,
    and `summary` the row's prose); or the catalogue row discover() makes for
    every managing club (`path` is reference/trail_orgs.json, its source).
    """

    club: str
    type: str
    path: Path
    claims: tuple[str, ...] = ()
    resources: tuple[Resource, ...] = ()
    shares: str | None = None
    note: NotAvailable | None = None
    same_as: tuple[SameAs, ...] = ()
    # A _shared/ input with no sources.json row says why here, and claims nothing:
    # its fetcher's own constant is its one home (ELT.md, "What moves").
    unregistered: str | None = None
    # A not_available.toml row's prose: the docstring its file carried before decision 88.
    summary: str | None = None

    @property
    def form(self) -> str:
        """Which shape the answer takes, or "invalid" when it takes none or several.

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

    @property
    def is_row(self) -> bool:
        """Whether this answer is a row of not_available.toml rather than a file of its own."""
        return self.path.name == NOT_AVAILABLE_FILE


def club_folders(root: Path = EXTRACT_DIR) -> list[Path]:
    """Every club folder under `root`: a directory not starting with `_` or `.`.

    A directory holding nothing but `__pycache__` is left out: it is what a
    deleted folder leaves on disk, which git does not hold (decision 88 left 42
    clubs with no folder, so a working tree that predates it keeps 42 of them).
    """
    return sorted(
        p
        for p in root.iterdir()
        if p.is_dir() and not p.name.startswith(("_", ".")) and any(child.name != "__pycache__" for child in p.iterdir())
    )


def managing_folders(trail_orgs: Path = TRAIL_ORGS_PATH) -> list[str]:
    """The folder of every managing club in trail_orgs.json (decision 18): each row whose `type` is not in NOT_CLUB_TYPES."""
    orgs = json.loads(trail_orgs.read_text(encoding="utf-8"))["orgs"]
    return sorted(folder_for_slug(row["slug"]) for row in orgs if row.get("type") not in NOT_CLUB_TYPES)


def _load_module(path: Path, club: str) -> ModuleType:
    """Import one club file by path. Club folders hold no __init__.py on purpose, so a folder is its type files alone."""
    spec = importlib.util.spec_from_file_location(f"extract.{club}.{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_club_file(path: Path, *, shared: bool = False) -> ClubFile:
    """One club file, whose type is its name; or, with `shared`, one _shared/ file.

    A _shared/ file is free-form, so its type is the `TYPE` it declares rather
    than its name, it never SHARES, and it may say UNREGISTERED. Its folder
    plays the club's part in the table name (`raw_<folder>__<key>`), which is
    why the layout test holds _shared/ folder names apart from club folder
    names. A file with no `TYPE` (a `notes.py`) declares no resource.
    """
    folder = path.parent.name
    module = _load_module(path, f"_shared.{folder}" if shared else folder)
    type_ = getattr(module, "TYPE", None) if shared else path.stem
    resources = tuple(replace(resource, club=folder, type=type_) for resource in getattr(module, "RESOURCES", ()) or ())
    return ClubFile(
        club=folder,
        type=type_,
        path=path,
        claims=tuple(getattr(module, "CLAIMS", ()) or ()),
        resources=resources,
        shares=None if shared else getattr(module, "SHARES", None),
        note=getattr(module, "NOT_AVAILABLE", None),
        same_as=tuple(getattr(module, "SAME_AS", ()) or ()),
        unregistered=getattr(module, "UNREGISTERED", None) if shared else None,
    )


def _row_value(path: Path, club: str, type_: str, row: dict, field: str, kind: type):
    """One field of a not_available.toml row, refused unless it is a `kind` (exactly, for a date and an int)."""
    value = row[field]
    # A TOML datetime is a date too, and a bool an int, so those two check the exact type.
    if (type(value) is not kind) if kind in (date, int) else not isinstance(value, kind):
        raise ValueError(f"{path.name} [{club}.{type_}]: `{field}` is {value!r}, which is not a {kind.__name__}")
    return value


def read_not_available(path: Path) -> list[ClubFile]:
    """Every row of not_available.toml, as the ClubFile its file gave before decision 88, in the file's order.

    A row holding `shares` is a share; any other row is a note. A field outside
    its kind's NOTE_FIELDS or SHARE_FIELDS, or of the wrong type, is refused
    here, naming the row. A note's `checked` and `where` default to empty so
    that NotAvailable.problems() names what is missing, row by row, in the
    layout test. A table written twice is TOML's own error: tomllib refuses it.
    """
    if not path.exists():
        return []
    rows = []
    for club, types in tomllib.loads(path.read_text(encoding="utf-8")).items():
        if not isinstance(types, dict) or not all(isinstance(row, dict) for row in types.values()):
            raise ValueError(f"{path.name}: [{club}] must hold one table per type, [{club}.<type>]")
        for type_, row in types.items():
            fields = SHARE_FIELDS if "shares" in row else NOTE_FIELDS
            if unknown := sorted(set(row) - fields):
                kind = "share" if "shares" in row else "note"
                raise ValueError(f"{path.name} [{club}.{type_}]: {unknown} is not a field of a {kind} row ({sorted(fields)})")
            summary = _row_value(path, club, type_, row, "summary", str) if "summary" in row else None
            if "shares" in row:
                shares = _row_value(path, club, type_, row, "shares", str)
                rows.append(ClubFile(club=club, type=type_, path=path, shares=shares, summary=summary))
                continue
            if "confirmed" not in row:
                raise ValueError(f"{path.name} [{club}.{type_}]: a note needs `confirmed`, the day a person looked")
            optional = {
                field: _row_value(path, club, type_, row, field, kind)
                for field, kind in (("recheck_after_days", int), ("terms", str), ("reason", str))
                if field in row
            }
            note = NotAvailable(
                confirmed=_row_value(path, club, type_, row, "confirmed", date),
                checked=tuple(_row_value(path, club, type_, row, "checked", list)) if "checked" in row else (),
                where=tuple(_row_value(path, club, type_, row, "where", list)) if "where" in row else (),
                **optional,
            )
            rows.append(ClubFile(club=club, type=type_, path=path, note=note, summary=summary))
    return rows


def discover(root: Path = EXTRACT_DIR, trail_orgs: Path = TRAIL_ORGS_PATH) -> list[ClubFile]:
    """Every managing club's answer for every type, ordered by club, then by `<type>.py`.

    The resource files in every club folder under `root`, the rows of its
    not_available.toml, and a catalogue row for every managing club in
    `trail_orgs` (decision 88). Nothing is merged: a type answered twice comes
    back twice, for the layout test to refuse.
    """
    from extract._kinds import catalogue_row  # extract/_kinds.py imports this module

    files = [read_club_file(path) for folder in club_folders(root) for path in sorted(folder.glob("*.py"))]
    files += read_not_available(root / NOT_AVAILABLE_FILE)
    catalogue = catalogue_row()
    files += [
        ClubFile(club=folder, type="org", path=trail_orgs, resources=(replace(catalogue, club=folder, type="org"),))
        for folder in managing_folders(trail_orgs)
    ]
    # Stable, so an answer given twice keeps the file before the row.
    return sorted(files, key=lambda club_file: (club_file.club, f"{club_file.type}.py"))


def shared_folders(root: Path = EXTRACT_DIR) -> list[Path]:
    """Every folder under _shared/: national services, aggregators and OurHike's own data (ELT.md, "_shared/")."""
    shared = root / SHARED_FOLDER
    if not shared.is_dir():
        return []
    return sorted(p for p in shared.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")))


def discover_shared(root: Path = EXTRACT_DIR) -> list[ClubFile]:
    """Every file in every _shared/ folder, in a stable order. not_clubs.py sits beside the folders and declares none."""
    return [read_club_file(path, shared=True) for folder in shared_folders(root) for path in sorted(folder.glob("*.py"))]


def all_resources(files: list[ClubFile]) -> list[Resource]:
    """Every Resource the club files declare. A share adds none: its sibling's resource is the one row."""
    return [resource for club_file in files for resource in club_file.resources]
