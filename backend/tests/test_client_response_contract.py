"""The response shapes the client declares, against the OpenAPI document (#316).

WHAT #487 LEFT

That change compared the *vocabularies* either side of this seam - report
types, reporter types, moderation statuses, preference values, the photo cap.
It deliberately did not touch the shape of a response, and said so. This is
that half: `ReportSummary`, `ClosureSummary`, `ProfileSummary`, `QueuedReport`
and `QueuedClosure` in `client/src/lib/api.ts` are hand-written TypeScript,
`api.test.ts` exercises them against hand-written mock bodies, and until now
nothing held either to what the server actually sends.

Against the DOCUMENT rather than the models, which is what #316 asked for and
is the stronger check by one link: `app.openapi()` is reached through the
route table, so a handler whose `response_model` was changed or dropped fails
here, while a check that imported `ReportOut` directly would go on comparing a
schema no endpoint serves any more. It is also the artifact a generated client
would be built from, so it is the thing whose accuracy is the actual promise.

THE RULE IS SUBSET, NOT EQUALITY, AND IN ONE DIRECTION

`ClosureSummary`'s own comment says it: "limited to the fields this app
reads." The client declaring fewer fields than the server sends is the
intended design, not drift - `ReportOut` carries `trail_id`, `follow_up` and
`received_at` that no screen reads. So a field on the server and not the
client is silence, and correct.

The failure is the other direction, and it is quiet in a way TypeScript
cannot help with: `response.json() as ReportSummary[]` is an assertion, not a
parse. A field the client declares and the server does not send is
`undefined` at runtime while the type says `string` - so `report.status`
renders as nothing, `closure.start_mile_marker` makes every comparison false,
and the app is confidently wrong rather than broken. Nullability is the same
failure one step in: a field the client declares `string` and the server
sends `null` for gets past every check the client has.

WHAT IS DELIBERATELY NOT CHECKED, AND WHY IT CANNOT BE (#502)

Type narrowing beyond scalars and nullability - a `string` gaining a pattern, a
number gaining a bound, an array gaining `minItems`.

The reason is not the one this note used to give. It said "detecting those well
means implementing JSON Schema subtyping", borrowing
`scripts/check_openapi_compat.py`'s argument, and that argument is a good one in
the file it came from. It does not apply here, because **this seam has nothing
to compare a narrowing against.** What it holds against `app.openapi()` are the
client's own declarations - TypeScript interfaces in `client/src/lib/api.ts` -
and a TypeScript interface carries no `maxLength`, no `minimum`, no `pattern`.
There is no client-side claim about a value's range for a server-side
constraint to contradict. Implementing narrowing detection here would mean
inventing constraints the client neither declares nor enforces, and then
testing the server against a fiction.

So this is where the decision #502 asked for is recorded: **this file stays as
it is, permanently, and not until somebody gets round to it.** The check that
CAN see a narrowing is `check_openapi_compat.py`, which compares two documents
rather than a document and a type - and as of #502 it reports request
constraints that appear or tighten, which is the subset needing no subtyping.

A field typed by name rather than inline (`reason_type: ClosureReason`) still
has its presence and nullability checked here and its VALUES checked below,
which between them is what a mismatch would actually cost.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.models.closure import ClosureStatus, ReasonType
from app.schemas.report import ReportCreate
from scripts.check_openapi_compat import current_document

CLIENT_SRC = Path(__file__).resolve().parents[2] / "client" / "src"
API = CLIENT_SRC / "lib" / "api.ts"
CLOSURE_BANNER = CLIENT_SRC / "lib" / "closureBanner.ts"
OUTBOX = CLIENT_SRC / "lib" / "outbox.ts"

# Read by tests/test_ci_scope.py - see CLIENT_FILES_READ in
# tests/test_client_report_contract.py for why this is declared rather than
# left implicit.
CLIENT_FILES_READ = (API, CLOSURE_BANNER, OUTBOX)


def _read(path: Path) -> str:
    assert path.exists(), (
        f"{path} is missing, so this test cannot compare anything. If the "
        "module moved, fix the path here rather than deleting the test."
    )
    return path.read_text()


class Field:
    """One declared field of a TypeScript interface."""

    def __init__(self, name: str, declared: str):
        self.name = name
        self.declared = declared.strip().rstrip(",")

    @property
    def nullable(self) -> bool:
        return bool(re.search(r"\bnull\b", self.declared))

    @property
    def scalar(self) -> str | None:
        """`string`, `number`, `boolean`, or None where it is not inferable.

        A quoted literal union (`'normal' | 'serious'`) is a string. A bare
        identifier (`ClosureReason`) is not resolved - see the module
        docstring for why that is deliberate rather than unfinished.
        """
        without_null = re.sub(r"\bnull\b", "", self.declared)
        if re.search(r"\bnumber\b", without_null):
            return "number"
        if re.search(r"\bboolean\b", without_null):
            return "boolean"
        if re.search(r"\bstring\b", without_null) or "'" in without_null:
            return "string"
        return None

    def __repr__(self) -> str:
        return f"{self.name}: {self.declared}"


def interface_fields(source: str, name: str) -> dict[str, Field]:
    """The fields of one `export interface`, following a single `extends`.

    `QueuedReport extends ReportSummary` and `PoiPhotoQueueEntry extends
    PoiPhotoSummary` are the only inheritance in that file and both are one
    level deep. Followed rather than ignored because the inherited fields
    are exactly the ones a moderation screen reads - skipping them would
    leave the widest consumers unchecked.
    """
    declaration = re.search(
        rf"export interface {name}(?: extends (\w+))? \{{\n(.*?)\n\}}",
        source,
        re.DOTALL,
    )
    assert declaration is not None, (
        f"Could not find `export interface {name}` in api.ts. If it was "
        "renamed or reformatted, fix the pattern here - do not delete this "
        "test, which is the only thing comparing the declared shape against "
        "what the server sends."
    )

    fields: dict[str, Field] = {}
    if declaration.group(1):
        fields.update(interface_fields(source, declaration.group(1)))

    # Two spaces, a name, a colon: the same field pattern
    # test_preferences_contract.py uses, and for the same reason - it excludes
    # JSDoc continuation lines, which are ` *` or deeper.
    for field in re.finditer(r"^  (\w+)\??: ([^\n]+)", declaration.group(2), re.MULTILINE):
        fields[field.group(1)] = Field(field.group(1), field.group(2))

    return fields


def _resolve(document: dict, schema: dict) -> dict:
    """Follow a `$ref` into `components.schemas`, once."""
    ref = schema.get("$ref")
    if ref is None:
        return schema
    return document["components"]["schemas"][ref.rsplit("/", 1)[-1]]


def response_schema(document: dict, path: str, *, unwrap: str | None = None) -> dict:
    """The object schema a `GET` on `path` answers with.

    Walks the document the way a client generator would - operation, 200,
    `application/json`, then through the array wrapper and the `$ref`. `unwrap`
    names a property to descend into first, which is what the moderation
    queue's `reports`/`closures` arrays need.
    """
    operation = document["paths"][path]["get"]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]

    if unwrap is not None:
        schema = _resolve(document, schema)["properties"][unwrap]

    if schema.get("type") == "array":
        schema = schema["items"]

    return _resolve(document, schema)


# Each client interface, and the endpoint whose body it is asserted onto.
# `QueuedReport`/`QueuedClosure` come off the same document node the client
# reads them from rather than from ReportOut/ClosureOut directly, so the
# moderation queue's own wrapper is part of what is checked.
SEAMS = [
    ("ReportSummary", "/reports", None),
    ("ClosureSummary", "/closures", None),
    ("ProfileSummary", "/profiles/me", None),
    ("QueuedReport", "/moderation/queue", "reports"),
    ("QueuedClosure", "/moderation/queue", "closures"),
    ("PoiPhotoSummary", "/waypoints/{poi_id}/photos", None),
    ("PoiPhotoQueueEntry", "/moderation/poi-photos", None),
]


@pytest.fixture(scope="module")
def document() -> dict:
    return current_document()


@pytest.mark.parametrize(("interface", "path", "unwrap"), SEAMS, ids=[s[0] for s in SEAMS])
def test_every_field_the_client_reads_is_one_the_server_sends(document, interface, path, unwrap):
    """The core assertion, in the one direction that is a defect.

    `as ReportSummary[]` is an assertion rather than a parse, so a field the
    server stopped sending is `undefined` behind a type that says otherwise -
    which renders as a blank status or a comparison that is silently false,
    not as an error anybody sees.
    """
    schema = response_schema(document, path, unwrap=unwrap)
    declared = interface_fields(_read(API), interface)

    missing = sorted(set(declared) - set(schema["properties"]))

    assert not missing, (
        f"client/src/lib/api.ts's {interface} declares fields that GET {path} "
        f"does not return:\n"
        + "\n".join(f"  - {name}: {declared[name].declared}" for name in missing)
        + f"\n\nThe response sends: {', '.join(sorted(schema['properties']))}"
    )


@pytest.mark.parametrize(("interface", "path", "unwrap"), SEAMS, ids=[s[0] for s in SEAMS])
def test_a_field_the_client_declares_non_null_is_required_and_never_null(document, interface, path, unwrap):
    """Nullability, which is the same failure one step further in.

    Only checked in the direction that hurts. A client declaring `string |
    null` where the server always sends a string is over-defensive and costs
    nothing; a client declaring `string` where the server can send `null` has
    a type that lies, and every branch it guards is wrong.
    """
    schema = response_schema(document, path, unwrap=unwrap)
    required = set(schema.get("required", []))
    problems = []

    for name, field in interface_fields(_read(API), interface).items():
        if field.nullable or name not in schema["properties"]:
            continue

        property_schema = schema["properties"][name]
        server_nullable = (
            any(option.get("type") == "null" for option in property_schema.get("anyOf", []))
            or property_schema.get("type") == "null"
        )

        if name not in required:
            problems.append(f"  - {name} is optional in the response, declared `{field.declared}`")
        elif server_nullable:
            problems.append(f"  - {name} can be null in the response, declared `{field.declared}`")

    assert not problems, (
        f"client/src/lib/api.ts's {interface} declares fields as always-present "
        f"that GET {path} does not guarantee:\n" + "\n".join(problems)
    )


@pytest.mark.parametrize(("interface", "path", "unwrap"), SEAMS, ids=[s[0] for s in SEAMS])
def test_the_scalar_types_agree_where_they_are_inferable(document, interface, path, unwrap):
    """`number` against `number`, and so on - the coarse check, deliberately.

    A mile marker typed `string` on one side and `number` on the other is not
    a type-system subtlety; it is `"1408.6" > 1407` being false. Fields typed
    by name rather than inline are skipped here and checked by value below.
    """
    schema = response_schema(document, path, unwrap=unwrap)
    problems = []

    for name, field in interface_fields(_read(API), interface).items():
        if field.scalar is None or name not in schema["properties"]:
            continue

        property_schema = schema["properties"][name]
        types = {property_schema["type"]} if "type" in property_schema else set()
        types |= {option.get("type") for option in property_schema.get("anyOf", [])}
        types.discard("null")
        types.discard(None)

        # An empty set is a `$ref` - an enum, which is a string on the wire
        # and is compared by value in the enum tests below.
        if types and field.scalar not in types:
            problems.append(f"  - {name}: client says `{field.declared}`, response says {sorted(types)}")

    assert not problems, f"{interface} and GET {path} disagree about types:\n" + "\n".join(problems)


# --- The closure vocabulary, which #487 did not reach ----------------------
#
# `ClosureReason` and `ClosureStatus` are declared in lib/closureBanner.ts and
# rendered through `REASON_LABELS`, a `Record<ClosureReason, string>` - so a
# value the server can send and the client has never heard of is an undefined
# label in a safety banner, on the one thing on this map whose absence a hiker
# would act on by walking into it.
#
# The direction that matters is server-to-client here, unlike the report
# vocabulary: the client never WRITES a closure (`ClosureCreate` is a
# maintainer tool), it only reads them. Set equality is still the assertion,
# because a value only the client knows is a label nothing can ever reach -
# which is dead code that looks like coverage.


def _client_union(source: str, name: str) -> set[str]:
    declaration = re.search(rf"export type {name} =(.*?)\n\n", source + "\n\n", re.DOTALL)
    assert declaration is not None, f"Could not find `export type {name} = ...`"
    return set(re.findall(r"'([^']+)'", declaration.group(1)))


@pytest.mark.parametrize(
    ("client_name", "server_enum"),
    [("ClosureReason", ReasonType), ("ClosureStatus", ClosureStatus)],
    ids=["ClosureReason", "ClosureStatus"],
)
def test_the_closure_vocabularies_match(client_name, server_enum):
    client = _client_union(_read(CLOSURE_BANNER), client_name)
    server = {member.value for member in server_enum}

    assert client == server, (
        f"client/src/lib/closureBanner.ts's {client_name} and "
        f"app/models/closure.py's {server_enum.__name__} have drifted. A "
        "reason the server sends and the banner has no label for renders as "
        "undefined on a closure warning.\n"
        f"  only in the client: {sorted(client - server)}\n"
        f"  only in the server: {sorted(server - client)}"
    )


# --- The request direction -------------------------------------------------


def test_every_field_the_outbox_sends_is_one_the_server_accepts():
    """The other half of the seam, and the one with a precedent.

    `ReportCreate` does not forbid extra keys, so a field the client sends and
    the schema has no name for is dropped in silence rather than refused -
    the failure #244 describes, where the form computed a mile and discarded
    it at submit, and the serious-warnings banner had nothing to filter on.

    Subset rather than equality: the server accepts `id` and `authored_at`
    that `ReportDraft` has no field for, because `sendReport` adds them from
    the outbox item itself rather than from the payload.
    """
    body = re.search(r"export interface ReportDraft \{\n(.*?)\n\}", _read(OUTBOX), re.DOTALL)
    assert body is not None, "Could not find `export interface ReportDraft`"

    sent = set(re.findall(r"^  (\w+)\??:", body.group(1), re.MULTILINE))
    accepted = set(ReportCreate.model_fields)

    unknown = sorted(sent - accepted)

    assert not unknown, (
        "client/src/lib/outbox.ts's ReportDraft carries fields ReportCreate "
        "has no name for. Unknown keys are ignored rather than refused, so "
        "these are written on the phone and dropped on arrival, with a 201 "
        "either way:\n" + "\n".join(f"  - {name}" for name in unknown)
    )


# --- Guarding the guards ---------------------------------------------------


def test_the_parser_is_actually_reading_the_client(document):
    """A regex that matched nothing would compare empty sets for ever."""
    report = interface_fields(_read(API), "ReportSummary")
    queued = interface_fields(_read(API), "QueuedReport")

    assert {"id", "status", "severity", "mile"} <= set(report)
    assert report["mile"].nullable
    assert not report["id"].nullable
    assert report["mile"].scalar == "number"
    assert report["id"].scalar == "string"
    assert report["severity"].scalar == "string", "a quoted literal union is a string"

    # The `extends` is followed, which is the one structural thing that would
    # silently halve this file's coverage if the pattern stopped matching.
    assert set(report) < set(queued)
    assert "visibility" in queued

    assert len(_client_union(_read(CLOSURE_BANNER), "ClosureReason")) >= 5


def test_the_document_really_describes_this_build(document):
    """Guards the other input.

    `current_document()` reaching an app with no routes would make every
    lookup above fail loudly rather than silently - but a document whose
    schemas had emptied would not, so this asserts on the shape the tests
    rely on.
    """
    assert set(document["paths"]) >= {"/reports", "/closures", "/profiles/me", "/moderation/queue"}
    assert {"ReportOut", "ClosureOut", "ProfileOut", "ModerationQueue"} <= set(document["components"]["schemas"])
    assert len(response_schema(document, "/reports")["properties"]) >= 10
