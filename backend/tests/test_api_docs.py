"""/docs and /redoc load their scripts at an exact version (#1918 item 9).

FastAPI's defaults pin jsdelivr to a major version only, so a new release of
swagger-ui-dist or redoc would run on this API's origin with no commit here.
app/main.py mounts both pages itself with exact versions; these tests read the
served HTML, so a FastAPI upgrade that changed how the pages are built cannot
quietly bring the floating URLs back.
"""

import re

from app.main import REDOC_JS, SWAGGER_UI_DIST

# `name@` followed by anything short of a full x.y.z, then a slash.
_FLOATING = re.compile(r"(swagger-ui-dist|redoc)@(\d+|\d+\.\d+)/")


def test_swagger_ui_loads_its_script_and_stylesheet_at_the_pinned_version(client):
    response = client.get("/docs")

    assert response.status_code == 200
    assert f"{SWAGGER_UI_DIST}/swagger-ui-bundle.js" in response.text
    assert f"{SWAGGER_UI_DIST}/swagger-ui.css" in response.text
    assert not _FLOATING.search(response.text)


def test_redoc_loads_its_script_at_the_pinned_version(client):
    response = client.get("/redoc")

    assert response.status_code == 200
    assert REDOC_JS in response.text
    assert not _FLOATING.search(response.text)


def test_both_pins_name_a_full_major_minor_patch_version():
    assert re.search(r"swagger-ui-dist@\d+\.\d+\.\d+$", SWAGGER_UI_DIST)
    assert re.search(r"redoc@\d+\.\d+\.\d+/", REDOC_JS)


def test_the_oauth2_redirect_page_swagger_ui_names_is_still_served(client):
    """FastAPI adds this route only alongside its own /docs, which app/main.py
    turns off, so the replacement has to mount it too."""
    assert client.get("/docs/oauth2-redirect").status_code == 200


def test_the_docs_pages_stay_out_of_the_published_schema(client):
    """`check_openapi_compat.py` compares /openapi.json against a baseline; a
    docs page leaking into it would read as three new API routes."""
    paths = client.get("/openapi.json").json()["paths"]

    assert not {"/docs", "/redoc", "/docs/oauth2-redirect"} & set(paths)
