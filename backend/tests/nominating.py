"""Getting a test past the three gates in front of the nominate flow.

The flow needs a signed-in hiker, a solved proof of work, and a fetch that
does not touch the network - in that order, on every call. Three test files
need all three (`test_routers_nominations.py`, `test_assist_consent.py`, and
anything added later), so the setup lives here rather than being written out
three times and drifting.

**THE CHALLENGE IS REALLY SOLVED HERE, not stubbed.** `solved()` runs the
backend's own `solve` against the backend's own `issue`, at the lowest
difficulty the module permits. A fixture that patched `verify` to return True
would leave every test green while the gate was wide open, which is the one
thing these tests exist to notice.
"""

from __future__ import annotations

from app.config import settings
from app.core.challenge import MIN_DIFFICULTY, issue, solve
from app.core.sitefetch import Link, Page
from app.core.time import utc_now

SECRET = "a challenge secret for the tests"

#: A club's contact page, with two addresses really on it. The reading is
#: checked back against these pages, so a test that wants a contact to survive
#: has to put it here - which is the property under test rather than an
#: inconvenience.
CONTACT_PAGE = Page(
    url="https://carolinamountainclub.org/get-involved",
    title="Get Involved - Carolina Mountain Club",
    text=(
        "Volunteer coordinator Dale Whitford - volunteers@carolinamountainclub.org. "
        "Trail data: Priya Raghavan, maps@carolinamountainclub.org. "
        "Our layer is at https://services.arcgis.com/abc/CMC_Trails/FeatureServer/0"
    ),
    links=(Link(href="mailto:volunteers@carolinamountainclub.org", text="Dale Whitford"),),
    emails=("volunteers@carolinamountainclub.org", "maps@carolinamountainclub.org"),
)

#: What a model plausibly answers about that page - including one contact that
#: is NOT on it, because the grounding check is the thing worth exercising by
#: default rather than on request.
MODEL_ANSWER = """{
  "org_name": "Carolina Mountain Club",
  "summary": "Asheville, NC.",
  "sources": [{"label": "ArcGIS FeatureServer",
               "url": "https://services.arcgis.com/abc/CMC_Trails/FeatureServer/0",
               "verdict": "usable", "detail": "line features"}],
  "contacts": [
    {"name": "Dale Whitford", "role": "Volunteer coordinator",
     "email": "volunteers@carolinamountainclub.org",
     "source_page": "https://carolinamountainclub.org/get-involved"},
    {"name": "Board President", "role": "Leadership",
     "email": "president@carolinamountainclub.org",
     "source_page": "https://carolinamountainclub.org/contact"}
  ]
}"""


def switch_on(monkeypatch):
    """The deployment settings the flow refuses to run without."""
    monkeypatch.setattr(settings, "nominate_challenge_secret", SECRET)
    monkeypatch.setattr(settings, "nominate_challenge_difficulty", MIN_DIFFICULTY)
    monkeypatch.setattr(settings, "assist_enabled", True)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test-not-a-real-key")
    return settings


def solved(hiker_id: str) -> dict:
    """A challenge for this hiker, with the work actually done."""
    challenge = issue(
        hiker_id,
        secret=SECRET,
        now=int(utc_now().timestamp()),
        difficulty=MIN_DIFFICULTY,
    )
    return {
        "nonce": challenge.nonce,
        "difficulty": challenge.difficulty,
        "expires_at": challenge.expires_at,
        "signature": challenge.signature,
        "solution": solve(challenge),
    }


def reads(monkeypatch, pages=(CONTACT_PAGE,)):
    """Hand the route these pages instead of opening a socket."""
    from app.routers import nominations as router

    monkeypatch.setattr(router, "read_site", lambda website, **kw: tuple(pages))


def answers(monkeypatch, text: str = MODEL_ANSWER, *, input_tokens: int = 100, output_tokens: int = 50):
    """Hand the route this answer instead of calling a model.

    Patches `ask` on the router rather than `httpx.post` beneath it, because
    what these tests are about is the flow's own decisions - the budget and
    the accounting have their own tests against the real `ask`.
    """
    from types import SimpleNamespace

    from app.routers import nominations as router

    def fake_ask(db, *, panel, system, prompt, club=None, counted_as=None):
        return SimpleNamespace(text=text, input_tokens=input_tokens, output_tokens=output_tokens)

    monkeypatch.setattr(router, "ask", fake_ask)
