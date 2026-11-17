"""A trailing slash answers 404, never a redirect (#1918 item 10).

Starlette's slash redirect builds its Location from the scheme uvicorn sees,
which behind Render's TLS proxy is plain http, so `GET /closures/` would have
sent a caller to an `http://` address. app/main.py turns the redirect off; no
route here is declared with a trailing slash, so it served no caller.
"""

import pytest
from fastapi.routing import APIRoute

from app.main import app


def _paths(routes):
    for route in routes:
        included = getattr(route, "original_router", None)
        if included is not None:
            yield from _paths(included.routes)
        elif isinstance(route, APIRoute):
            yield route.path


@pytest.mark.parametrize("path", ["/closures/", "/reports/", "/health/"])
def test_a_slash_form_is_a_404_with_no_location(client, path):
    response = client.get(path, follow_redirects=False)

    assert response.status_code == 404
    assert "location" not in response.headers


def test_the_slash_less_form_still_answers(client):
    assert client.get("/closures").status_code == 200


def test_no_route_is_declared_with_a_trailing_slash():
    """The redirect was safe to drop only because every route is declared
    without one. A route added as `@router.get("/")` under a prefix would be
    reachable only at the slash form, which callers do not send."""
    assert [path for path in _paths(app.routes) if path != "/" and path.endswith("/")] == []
