"""The two halves of `UserPreferences`, compared against each other.

`client/src/lib/userPreferences.ts` and `app/schemas/preferences.py` are the
same model written twice in two languages, and each file's header says so -
the client's promises "the field names here match that contract exactly", and
`PreferencesIn` sets `extra="forbid"` so that an invented key "becomes a real
422 ... rather than the field being silently dropped."

Nothing compared them. `wrong_way_alert_enabled` was added to the client and
not to the schema, and both files went on asserting they matched (#242). The
sync is a FULL-BLOB `PUT /preferences/me` - "a client syncing its whole local
UserPreferences state wholesale", per the router - so one unknown key does not
cost one field. It costs the entire sync, for every hiker, on the first
attempt, for ever.

It has not fired yet only because nothing in the client calls the endpoint
(`grep -rn "preferences/me" client/src` finds nothing). The drift was waiting
for #231's PUT to land on top of it.

**Reading the TypeScript as text is the point, not a shortcut.** Any check
that restated the field list here in Python would be a third copy to keep in
step, and the bug being guarded against is exactly a copy falling out of step.
The one thing this must never do is pass because it failed to find the file.
"""

import re
from pathlib import Path

import pytest

from app.schemas.preferences import (
    BackgroundSource,
    HikingDetailLevel,
    LayerDetailLevel,
    MapStyle,
    MaxBackgroundZoom,
    PreferencesIn,
    PreferencesOut,
    Theme,
    UnitSystem,
)

CLIENT_MODEL = Path(__file__).resolve().parents[2] / "client" / "src" / "lib" / "userPreferences.ts"

# The interface body, from its opening brace to the first line that closes it
# at column zero. Deliberately not a brace counter: nothing nests inside this
# interface, and a parser that could be wrong in an interesting way is a worse
# thing to own than one that fails loudly the day somebody nests something.
_INTERFACE = re.compile(r"export interface UserPreferences \{\n(.*?)\n\}", re.DOTALL)

# A field line: exactly two spaces, a name, a colon. Two spaces excludes the
# contents of JSDoc blocks and multi-line comments, whose continuation lines
# are ` *` or deeper.
_FIELD = re.compile(r"^  (\w+)\??:", re.MULTILINE)


def client_fields() -> set[str]:
    assert CLIENT_MODEL.exists(), (
        f"{CLIENT_MODEL} is missing, so this test cannot compare anything. "
        "It fails rather than skips: a guard that quietly stops looking is "
        "worse than no guard, because the suite still reports green."
    )

    body = _INTERFACE.search(CLIENT_MODEL.read_text())
    assert body is not None, (
        "Could not find `export interface UserPreferences { ... }` in "
        f"{CLIENT_MODEL}. If it was renamed or reformatted, fix the pattern "
        "here - do not delete this test, which is the only thing comparing "
        "the two halves of the model."
    )

    return set(_FIELD.findall(body.group(1)))


def test_the_two_halves_of_the_model_declare_the_same_fields():
    """Set equality, in both directions, and both directions matter.

    A key the client has and the schema does not is a 422 that rejects the
    whole blob (#242). A key the schema has and the client does not is a
    preference nobody can ever set: it would be filled from its default on
    every sync and silently overwrite anything a future client wrote.
    """
    client = client_fields()
    server = set(PreferencesIn.model_fields)

    assert client == server, (
        "client/src/lib/userPreferences.ts and app/schemas/preferences.py "
        "have drifted apart, and the sync is a full-blob PUT - so this is not "
        "one field going missing, it is every sync failing.\n"
        f"  only in the client: {sorted(client - server)}\n"
        f"  only in the schema: {sorted(server - client)}"
    )


def test_that_comparison_is_actually_reading_the_client():
    """Guards the guard.

    A regex that matched nothing would make the test above compare an empty
    set against an empty set - green for ever, while the model drifted. Two
    specific, long-standing field names, so this fails loudly if the parse
    silently stops working rather than if somebody merely adds a field.
    """
    fields = client_fields()

    assert len(fields) >= 15
    assert "trail_name" in fields
    assert "anonymity_window_days" in fields


def test_a_key_the_client_invents_is_still_refused():
    """The `extra="forbid"` half, asserted rather than assumed.

    This is what turns drift into a loud 422 instead of a field silently
    dropped on the floor - and it is the reason the test above has to hold,
    since forbidding extras is only safe if the two lists agree.
    """
    payload = {name: None for name in PreferencesIn.model_fields}

    with pytest.raises(Exception) as refused:
        PreferencesIn(**payload, invented_by_a_future_client=True)

    assert "invented_by_a_future_client" in str(refused.value)


def test_the_wrong_way_alert_preference_survives_a_round_trip():
    """The field the drift was about (#242).

    Asserted through the schema rather than the endpoint because what broke
    was the contract, not the handler: `PreferencesIn` refusing the key is
    what made every PUT fail.
    """
    stored = PreferencesIn(
        background_source="hiking_topo_live",
        max_background_zoom=12,
        layer_detail_level="standard",
        anonymity_window_days=0,
        wrong_way_alert_enabled=False,
    ).model_dump(mode="json")

    assert stored["wrong_way_alert_enabled"] is False
    assert PreferencesIn(**stored).wrong_way_alert_enabled is False


def test_a_row_stored_before_the_key_existed_reads_back_as_the_safety_default():
    """The alert is opt-out, so an absent key must mean ON.

    `GET /preferences/me` builds a PreferencesOut straight from the stored
    JSON blob, and blobs written before this key existed simply do not have
    it. Defaulting to False there would silently disable the one notification
    this app sends, for every hiker who synced early - which is the failure
    mode syncing the preference at all was meant to avoid.
    """
    from datetime import datetime, timezone

    older_blob = {
        "trail_name": None,
        "background_source": "hiking_topo_live",
        "max_background_zoom": 12,
        "layer_detail_level": "standard",
        "anonymity_window_days": 0,
    }

    restored = PreferencesOut(**older_blob, updated_at=datetime.now(timezone.utc))

    assert restored.wrong_way_alert_enabled is True


# --- The values, not only the field names ----------------------------------
#
# The comparison above is about KEYS, and it caught the drift #242 was about.
# It cannot see the other half. `PreferencesIn` validates every enum field, so
# a value the client can store and the schema does not accept fails exactly
# the way an unknown key does: a 422 on a full-blob PUT, which is not one
# preference lost but the entire sync refused, on every attempt, for as long
# as the hiker holds that setting.
#
# The client's own comments already promise this. `MAP_STYLE_VALUES` says
# "the backend's enum mirrors this exactly", `BACKGROUND_SOURCES` says "a
# value nothing can render is also a value nothing can sync", and
# `HIKING_DETAIL_LEVEL_VALUES` says "the backend's `HikingDetailLevel`
# mirrors this exactly". Three promises, none of them checked - and the map
# styles are the likely first break, because adding one is a client-side
# design change that has no reason to open a Python file.
#
# Both directions fail, as with the keys. A value only the server knows is a
# setting nobody can choose, which is how a half-landed feature looks finished
# from either file alone.
#
# `reporter_type` is deliberately absent here: it is shared with the report
# wire format as well, so all three copies are compared together in
# tests/test_client_report_contract.py rather than twice, differently.

_VALUES_CONST = r"export const {name} = \[(.*?)\] as const"
_TYPE_UNION = r"export type {name} =([^\n]*)"


def client_values(name: str) -> set[str]:
    """One client-side vocabulary, however that file happens to spell it.

    Two spellings are in use and both are deliberate: a `const [...] as const`
    where something needs the list at RUNTIME (the pickers, and
    `preferences.ts` dropping stored values this build does not know), and a
    bare union where only the type is wanted. This reads either, and fails
    loudly rather than returning an empty set if it recognises neither -
    an empty set would compare equal to nothing and green for ever.
    """
    source = CLIENT_MODEL.read_text()

    for pattern in (_VALUES_CONST, _TYPE_UNION):
        found = re.search(pattern.format(name=name), source, re.DOTALL)
        if found is not None and (values := set(re.findall(r"'([^']+)'", found.group(1)))):
            return values

    raise AssertionError(
        f"Could not read the values of `{name}` from {CLIENT_MODEL}. If it was "
        "renamed or reformatted, fix the pattern here - do not delete this "
        "test, which is the only thing comparing the two vocabularies."
    )


@pytest.mark.parametrize(
    ("client_name", "server_enum"),
    [
        ("THEME_VALUES", Theme),
        ("UnitSystem", UnitSystem),
        ("MAP_STYLE_VALUES", MapStyle),
        ("BACKGROUND_SOURCES", BackgroundSource),
        ("LayerDetailLevel", LayerDetailLevel),
        ("HIKING_DETAIL_LEVEL_VALUES", HikingDetailLevel),
    ],
    ids=lambda item: item if isinstance(item, str) else item.__name__,
)
def test_the_two_halves_offer_the_same_values(client_name, server_enum):
    client = client_values(client_name)
    server = {member.value for member in server_enum}

    assert client == server, (
        f"client/src/lib/userPreferences.ts's {client_name} and "
        f"app/schemas/preferences.py's {server_enum.__name__} have drifted. "
        "The sync is a full-blob PUT, so a value only the client knows is "
        "every sync failing for whoever chose it.\n"
        f"  only in the client: {sorted(client - server)}\n"
        f"  only in the schema: {sorted(server - client)}"
    )


def test_the_background_zoom_ceilings_match():
    """The one vocabulary written as numbers rather than strings.

    Its own test because the values ARE the zoom levels - `max_background_zoom`
    stores the ceiling rather than a tier name (`detailLevelForZoom` in
    lib/downloadDetail.ts reads the choice back out of it) - so a mismatch
    here is a hiker's downloaded detail silently changing, not just a refused
    sync.
    """
    declaration = re.search(r"export type MaxBackgroundZoom = ([\d |]+)\n", CLIENT_MODEL.read_text())
    assert declaration is not None, "Could not find `export type MaxBackgroundZoom = ...`"

    client = {int(value) for value in re.findall(r"\d+", declaration.group(1))}
    server = {member.value for member in MaxBackgroundZoom}

    assert client == server, f"MaxBackgroundZoom: client {sorted(client)}, schema {sorted(server)}"


def test_the_value_reader_is_actually_reading_the_client():
    """Guards the guard above, the way the field reader already has one."""
    assert "auto" in client_values("THEME_VALUES")
    assert "night_hike" in client_values("MAP_STYLE_VALUES")
    assert len(client_values("MAP_STYLE_VALUES")) >= 5

    with pytest.raises(AssertionError):
        client_values("NoSuchVocabularyExistsHere")


def test_a_value_the_client_invents_is_refused_by_the_schema():
    """What drift costs, asserted rather than described - the value-level
    twin of `test_a_key_the_client_invents_is_still_refused`."""
    with pytest.raises(Exception) as refused:
        PreferencesIn(
            background_source="hiking_topo_live",
            max_background_zoom=12,
            layer_detail_level="standard",
            anonymity_window_days=0,
            map_style="aurora",
        )

    assert "map_style" in str(refused.value)
