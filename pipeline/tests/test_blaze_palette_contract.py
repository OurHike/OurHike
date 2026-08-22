"""The palette, compared against the client that paints it (#782).

features/NEARBY_TRAILS.md section 4 asks for a palette that is CLOSED and
grows by review. Closed only means something if both halves agree on what is
in it: `lib/blaze.py`'s `PALETTE` decides which mapping rows a reviewed file
may contain, and `client/src/lib/blaze.ts`'s `BLAZE_COLORS` decides what
actually gets painted. Two lists, no shared package, so this is the guard -
the same shape `test_published_key_contract.py` and #831's resolver fixtures
already use, and pipeline-tests.yml's scope list carries the TypeScript file
so editing it runs this suite.

WHAT DRIFT WOULD ACTUALLY COST

Not a crash. A mapping row naming a member the client dropped renders every
trail wearing that paint as neutral grey, which is indistinguishable from
"this source had no blaze data" - the exact silent-wrong that the loud
pipeline warning exists to prevent, arriving through the one path the warning
cannot see. And a member admitted to the client and missing here is a paint
no source can ever be mapped onto, which reads as the admission having been
forgotten halfway.
"""

import re
from pathlib import Path

from lib.blaze import NEUTRAL_MEMBERS, PALETTE

CLIENT_BLAZE = Path(__file__).resolve().parents[2] / "client" / "src" / "lib" / "blaze.ts"


def client_palette() -> list[str]:
    """The member names out of `BLAZE_COLORS`, in declaration order.

    Read as text rather than parsed, for the reason
    `backend/tests/test_preferences_contract.py` gives about the same trick:
    any check that restated the list in Python would be a third copy to keep
    in step, and a copy falling out of step is the whole bug.
    """
    source = CLIENT_BLAZE.read_text(encoding="utf-8")
    body = re.search(r"const BLAZE_COLORS: Record<string, string> = \{(.*?)\n\}", source, re.S)
    assert body is not None, (
        "Could not find BLAZE_COLORS in client/src/lib/blaze.ts. If it was renamed or reshaped, "
        "this contract needs updating rather than deleting - see this module's docstring."
    )
    return re.findall(r"^\s{2}(\w+):", body.group(1), re.M)


def test_the_two_palettes_name_the_same_paints():
    assert sorted(PALETTE) == sorted(name for name in client_palette() if name not in NEUTRAL_MEMBERS)


def test_the_client_still_answers_for_every_neutral_this_module_allows():
    """A mapping row may legitimately name a neutral - "this source's blank
    means confirmed-unblazed" is a real reviewed decision - so the client has
    to have an entry for each, or that row paints nothing and warns."""
    assert set(NEUTRAL_MEMBERS) <= set(client_palette())


def test_the_contract_can_see_the_file_it_claims_to():
    """A guard on the guard: an empty read would make both tests above pass
    by comparing nothing, which is the one way this file could be worse than
    not existing."""
    found = client_palette()
    assert len(found) >= 8, f"only found {found} in the client palette"
    assert "Aqua" in found, "Aqua is #782's first admission and should be in the client palette"
