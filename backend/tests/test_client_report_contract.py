"""The report vocabulary, compared against the client that speaks it.

`tests/test_preferences_contract.py` already does this for preferences, and
its header explains why reading the TypeScript as text is the point rather
than a shortcut: any check that restated the list here in Python would be a
third copy to keep in step, and a copy falling out of step is the whole bug.
This file is the same guard over the other model the two ends share - the
report - and over the one number the client is told to duplicate.

WHY REPORTS NEED IT AS MUCH AS PREFERENCES DID

`ReportType`, `ReporterType` and `ReportStatus` are written twice, in
`app/models/report.py` and in `client/src/lib/outbox.ts` /
`client/src/lib/reportStatus.ts`, and each side's comments claim to mirror
the other. Nothing compared them. The three drift in three different shapes,
and none of them is quiet:

  - A `type` the client can send and the schema does not accept is a 422 on
    submit. The outbox marks that item `failure` and stops retrying it
    (`lib/outbox.ts`), so it is not a report that arrives late - it is a
    report that never arrives, for the one category the drift touched.
  - A `reporter_type` that disagrees fails the same way, but for every report
    a hiker files rather than for one category, because the field is on all
    of them.
  - A `status` the server can return and `REPORT_STATE_WORDS` has no entry
    for renders as `undefined` in the reporter's own queue - the one place a
    hiker looks to find out whether anyone acted on what they filed.

The submit path has no fallback to soften any of that: unlike the enums
`scripts/check_openapi_compat.py` allows to grow (rendered through a lookup
with a neutral default), these three are read directly.

The photo cap is the same class of duplication with an explicit note asking
for this test - `lib/reportPhoto.ts` says the limit is "deliberately
duplicated ... rather than fetched", that "if the two ever disagree the
server wins and the upload is refused", and that this is "a bug worth having
loudly". Loudly is here, before a hiker's photo is the thing that finds it.

WHAT THIS DOES NOT CHECK

`Visibility` and `Severity`. Both are server-controlled, the client never
sends either, and `reportStatus.ts` deliberately renders no penalty state -
so there is no second copy to drift.
"""

import re
from pathlib import Path

import pytest

from app.core.photos import MAX_PHOTO_BYTES
from app.models.report import ReporterType, ReportStatus, ReportType
from app.schemas.report import ReportCreate

CLIENT_SRC = Path(__file__).resolve().parents[2] / "client" / "src"
OUTBOX = CLIENT_SRC / "lib" / "outbox.ts"
REPORT_STATUS = CLIENT_SRC / "lib" / "reportStatus.ts"
REPORT_PHOTO = CLIENT_SRC / "lib" / "reportPhoto.ts"


def _read(path: Path) -> str:
    """The client file, or a failure that says which one is missing.

    Fails rather than skips, for the reason test_preferences_contract.py
    states: a guard that quietly stops looking is worse than no guard,
    because the suite still reports green.
    """
    assert path.exists(), (
        f"{path} is missing, so this test cannot compare anything. If the "
        "module moved, fix the path here - do not delete the test, which is "
        "the only thing holding these two vocabularies together."
    )
    return path.read_text()


def _quoted(text: str) -> set[str]:
    """Every single-quoted literal in a slice of TypeScript."""
    return set(re.findall(r"'([^']*)'", text))


def _interface_field_union(source: str, interface: str, field: str) -> set[str]:
    """The string literals of one field's union inside one interface.

    The union is written across several lines with prose between the arms
    (`ReportDraft['type']` carries two paragraphs of it), so the slice runs
    from the field's own line to the next field's, and the literals are read
    out of it. Comment text cannot contribute: the arms are quoted and the
    prose is not.
    """
    body = re.search(rf"export interface {interface} \{{\n(.*?)\n\}}", source, re.DOTALL)
    assert body is not None, (
        f"Could not find `export interface {interface} {{ ... }}`. If it was "
        "renamed or reformatted, fix the pattern here rather than deleting "
        "the test."
    )

    fields = list(re.finditer(r"^  (\w+)\??:", body.group(1), re.MULTILINE))
    for index, match in enumerate(fields):
        if match.group(1) != field:
            continue
        end = fields[index + 1].start() if index + 1 < len(fields) else len(body.group(1))
        return _quoted(body.group(1)[match.start() : end])

    raise AssertionError(f"`{interface}` has no `{field}` field - it was renamed or removed")


def _type_union(source: str, name: str) -> set[str]:
    """`export type Name = 'a' | 'b'`, on one line or several."""
    declaration = re.search(rf"export type {name} =(.*?)\n\n", source + "\n\n", re.DOTALL)
    assert declaration is not None, f"Could not find `export type {name} = ...`"
    return _quoted(declaration.group(1))


def _number_constant(source: str, name: str) -> int:
    """`export const NAME = <arithmetic>` evaluated as the number it spells.

    The client writes its cap as `2 * 1024 * 1024`, which is the same number
    this module writes the same way. Comparing the VALUES rather than the
    text is what lets either side rewrite `2 * 1024 * 1024` as `2_097_152`
    without failing a test about something else.
    """
    declaration = re.search(rf"export const {name} = ([0-9_ */+]+)\n", source)
    assert declaration is not None, f"Could not find `export const {name} = ...`"
    return int(eval(declaration.group(1), {"__builtins__": {}}, {}))  # noqa: S307 - digits and operators only


# --- The three vocabularies ------------------------------------------------


def test_the_client_can_only_file_report_types_the_server_accepts():
    """Set equality, and both directions are a defect.

    A type only the client knows is a 422 the outbox gives up on. A type only
    the server knows is a category nobody can file, which is how a report
    type ships half-built and looks finished from either file alone.
    """
    client = _interface_field_union(_read(OUTBOX), "ReportDraft", "type")
    server = {member.value for member in ReportType}

    assert client == server, (
        "client/src/lib/outbox.ts and app/models/report.py disagree about "
        "what a report can be. A type the client sends and the server "
        "refuses is a 422 the outbox marks failed and stops retrying.\n"
        f"  only in the client: {sorted(client - server)}\n"
        f"  only in the server: {sorted(server - client)}"
    )


def test_both_halves_spell_the_reporter_types_the_same_way():
    """Three copies, not two - and the third is the durable one.

    `lib/userPreferences.ts` holds `REPORTER_TYPE_VALUES` as the stored
    preference and says so explicitly ("declared here rather than imported
    from lib/outbox.ts ... the two are held together by
    lib/reporterIdentity.ts"). That separation is deliberate and worth
    keeping; what it needs is for all three to agree, since the stored value
    is what the outbox puts on the wire.
    """
    outbox = _interface_field_union(_read(OUTBOX), "ReportDraft", "reporter_type")
    preferences = _quoted(
        re.search(
            r"export const REPORTER_TYPE_VALUES = \[(.*?)\]",
            _read(CLIENT_SRC / "lib" / "userPreferences.ts"),
            re.DOTALL,
        ).group(1)
    )
    server = {member.value for member in ReporterType}

    assert outbox == server, f"outbox.ts vs app/models/report.py: {outbox ^ server}"
    assert preferences == server, f"userPreferences.ts vs app/models/report.py: {preferences ^ server}"


def test_every_status_the_server_can_return_has_a_word_for_the_reporter():
    """`REPORT_STATE_WORDS` is a total map, and stays one.

    Written as a `Record<BackendReportStatus, ReportStateWord>`, so
    TypeScript already forces every key of the union to be present - which
    means the union is the thing that can drift, and the lookup silently
    follows it. A status returned by the server and absent from the union
    reaches `reportStateFor` as an unhandled key and renders `undefined`.
    """
    source = _read(REPORT_STATUS)
    client = _type_union(source, "BackendReportStatus")
    server = {member.value for member in ReportStatus}

    assert client == server, (
        "client/src/lib/reportStatus.ts and app/models/report.py disagree "
        "about the moderation vocabulary. A status with no word for it "
        "renders as undefined in the reporter's own queue.\n"
        f"  only in the client: {sorted(client - server)}\n"
        f"  only in the server: {sorted(server - client)}"
    )

    table = re.search(r"REPORT_STATE_WORDS[^{]*\{(.*?)\n\}", source, re.DOTALL)
    assert table is not None, "Could not find the REPORT_STATE_WORDS table"
    mapped = set(re.findall(r"^  (\w+):", table.group(1), re.MULTILINE))

    assert mapped == server, (
        "REPORT_STATE_WORDS does not cover the server's statuses exactly - "
        f"missing {sorted(server - mapped)}, extra {sorted(mapped - server)}"
    )


def test_the_client_refuses_a_photo_at_the_same_size_the_server_does():
    """The one number lib/reportPhoto.ts asks to be held to.

    A client cap ABOVE the server's is the failure with a cost: the phone
    encodes, stores and uploads bytes the server then refuses, on the signal
    a hiker had to walk to find. Equality rather than `<=` because the client
    comment says it is restating this exact limit - a client that quietly
    aimed lower would be a different decision, and one worth writing down
    rather than discovering here.
    """
    client = _number_constant(_read(REPORT_PHOTO), "MAX_PHOTO_BYTES")

    assert client == MAX_PHOTO_BYTES, (
        "client/src/lib/reportPhoto.ts and app/core/photos.py disagree about "
        f"the photo cap: client {client:,} bytes, server {MAX_PHOTO_BYTES:,}. "
        "The client's comment says it is restating the server's limit so it "
        "can refuse locally with no signal."
    )


# --- Guarding the guards ---------------------------------------------------


def test_the_parsers_are_actually_reading_the_client():
    """A regex that matched nothing would compare two empty sets for ever.

    Named literals rather than counts, and long-standing ones, so this fails
    when the parse stops working rather than when somebody adds a category.
    """
    types = _interface_field_union(_read(OUTBOX), "ReportDraft", "type")
    statuses = _type_union(_read(REPORT_STATUS), "BackendReportStatus")

    assert "blowdown" in types
    assert "thanks" in types
    assert len(types) >= 7
    assert "submitted" in statuses
    assert len(statuses) >= 4
    assert _number_constant(_read(REPORT_PHOTO), "MAX_PHOTO_BYTES") > 0


def test_a_type_the_client_invented_is_refused_by_the_schema():
    """What drift actually costs, asserted rather than described.

    The comparison above is only worth running if a mismatch really is a
    rejection - so this files the report a drifted client would file.
    """
    with pytest.raises(Exception) as refused:
        ReportCreate(type="rockfall", reporter_type="thru")

    assert "type" in str(refused.value)
