"""What a shared cache in front of the API may keep (app/core/edge_cache.py).

Each of these would otherwise be invisible until production, where a
Cloudflare cache sits between every hiker and this process: which routes are
shared, that a signed-in answer never is, that a shared copy answers a browser
whatever request filled it, that an error is never marked shareable, and that
the daily check in pipeline/check_deployment.py expects the header these
routes send.
"""

import ast
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.core.edge_cache import EDGE_TTL_SECONDS, NO_STORE, PRIVATE, SHARED, NoStoreByDefaultMiddleware, shared_at_edge
from app.db.session import get_db
from app.main import app
from app.models.closure import Closure, ModerationStatus
from app.models.profile import Role
from tests.factories import make_profile
from tests.tokens import auth_headers

SHARED_ROUTES = {("GET", "/closures"), ("GET", "/reports"), ("GET", "/disputes")}

REPO_ROOT = Path(__file__).resolve().parents[2]

# Read as text, the way tests/test_conditions_publisher_contract.py reads the
# conditions publisher: the pipeline is not importable from here (its own
# package and dependencies). Declared as a set so tests/test_ci_scope.py can
# hold the workflow's scope list to it.
PIPELINE_FILES_READ = {REPO_ROOT / "pipeline" / "check_deployment.py"}

CHECK_DEPLOYMENT = next(iter(PIPELINE_FILES_READ))


def _api_routes(routes):
    """Every APIRoute, descending through `original_router`: this FastAPI
    wraps each `include_router` in an `_IncludedRouter`, so `app.routes` alone
    reaches only `/health`, `/ready` and the docs (the same walk as
    tests/test_routers_reports.py's report guard)."""
    for route in routes:
        included = getattr(route, "original_router", None)
        if included is not None:
            yield from _api_routes(included.routes)
        elif isinstance(route, APIRoute):
            yield route


def test_the_edge_shares_closures_reports_and_disputes_and_no_other_route():
    shared = {
        (method, route.path)
        for route in _api_routes(app.routes)
        if any(dep.dependency is shared_at_edge for dep in route.dependencies)
        for method in route.methods
    }

    # A fourth route belongs here only once its answer is the same for every
    # anonymous caller and embeds no signed URL. /field-notes and
    # /waypoints/{poi_id}/photos embed presigned photo URLs, which
    # app/core/photos.py forbids any shared cache from keeping.
    assert shared == SHARED_ROUTES


def test_the_route_walk_reaches_the_routers_so_the_list_above_is_not_vacuous():
    paths = {route.path for route in _api_routes(app.routes)}

    assert {"/closures", "/reports", "/disputes", "/field-notes", "/moderation/queue"} <= paths


def test_the_shared_policy_lets_only_the_edge_keep_a_copy_for_five_minutes():
    assert EDGE_TTL_SECONDS == 300
    assert SHARED == "public, max-age=0, s-maxage=300"


def _pinned_in_check_deployment(name: str):
    for node in ast.parse(CHECK_DEPLOYMENT.read_text()).body:
        if isinstance(node, ast.Assign) and any(getattr(target, "id", None) == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(
        f"{name} not found in {CHECK_DEPLOYMENT}. If the daily check stopped pinning the shared reads' "
        "Cache-Control, or renamed it, fix this test rather than deleting it - it is what keeps that check "
        "expecting the header these routes send."
    )


def test_the_daily_edge_check_expects_the_cache_control_these_reads_send():
    """pipeline/check_deployment.py fails a copy of GET /closures carrying any
    Cache-Control but SHARED, and takes its Age bound from SHARED's s-maxage.
    It cannot import this module (the pipeline's requirements carry no
    FastAPI), so it pins the string. A change to SHARED or EDGE_TTL_SECONDS
    made here alone would turn that check red every day from the deploy on,
    or hold the edge to a lifetime the API no longer asks for."""
    assert _pinned_in_check_deployment("BACKEND_SHARED_CACHE_CONTROL") == SHARED


def test_anonymous_closures_reports_and_disputes_reads_are_marked_shareable(client):
    for _, path in sorted(SHARED_ROUTES):
        response = client.get(path)

        assert response.status_code == 200, path
        assert response.headers["cache-control"] == SHARED, path


def test_a_shared_copy_carries_allow_origin_even_when_the_request_sent_no_origin(client):
    # The request a monitor or curl makes. Starlette's CORS layer adds nothing
    # without an Origin, and a copy cached from this request is what the next
    # five minutes of browsers would be handed.
    response = client.get("/closures")

    assert "origin" not in {name.lower() for name in response.request.headers}
    assert response.headers.get_list("access-control-allow-origin") == ["*"]


def test_a_shared_copy_requested_by_a_browser_carries_exactly_one_allow_origin(client):
    response = client.get("/closures", headers={"Origin": "https://ourhike.org"})

    assert response.headers.get_list("access-control-allow-origin") == ["*"]


def test_a_signed_in_read_of_a_shared_route_is_never_shareable(client, db_session):
    profile = make_profile(db_session, Role.hiker)

    for _, path in sorted(SHARED_ROUTES):
        response = client.get(path, headers=auth_headers(profile.id))

        assert response.status_code == 200, path
        assert response.headers["cache-control"] == PRIVATE, path


def test_field_notes_and_waypoint_photos_stay_uncached_because_they_embed_signed_photo_urls(client):
    for path in ("/field-notes", "/waypoints/atc_shelters:abc123/photos"):
        response = client.get(path)

        assert response.status_code == 200, path
        assert response.headers["cache-control"] == NO_STORE, path


def test_every_route_that_chose_no_policy_answers_no_store(client):
    for path in ("/health", "/clubs", "/no-such-route"):
        response = client.get(path)

        assert response.headers["cache-control"] == NO_STORE, path


def test_an_error_on_a_shared_route_is_never_marked_shareable_so_the_edge_never_keeps_it(db_engine):
    def unreachable_database():
        raise RuntimeError("the pooler refused the connection")

    app.dependency_overrides[get_db] = unreachable_database
    try:
        response = TestClient(app, raise_server_exceptions=False).get("/closures")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    assert "public" not in response.headers.get("cache-control", "")


def test_no_store_by_default_keeps_a_policy_the_route_already_set():
    async def own_policy(_request):
        return PlainTextResponse("signed", headers={"Cache-Control": "private, no-store, max-age=0"})

    async def no_policy(_request):
        return PlainTextResponse("plain")

    inner = Starlette(routes=[Route("/own", own_policy), Route("/none", no_policy)])
    wrapped = TestClient(NoStoreByDefaultMiddleware(inner))

    assert wrapped.get("/own").headers["cache-control"] == "private, no-store, max-age=0"
    assert wrapped.get("/none").headers["cache-control"] == NO_STORE


def test_a_closures_list_past_500_bytes_is_gzipped_for_a_caller_that_accepts_it(client, db_session):
    reporter = make_profile(db_session, Role.hiker)
    db_session.add_all(
        Closure(
            reported_by=reporter.id,
            reason_type="storm_damage",
            start_mile_marker=float(mile),
            end_mile_marker=float(mile) + 0.5,
            note="Blowdowns across the treadway after the October storm; detour on the blue blaze.",
            moderation_status=ModerationStatus.verified,
        )
        for mile in range(10, 20)
    )
    db_session.commit()

    response = client.get("/closures", headers={"Accept-Encoding": "gzip"})

    assert response.status_code == 200
    assert len(response.content) > 500
    assert response.headers["content-encoding"] == "gzip"
    assert len(response.json()) == 10
