"""The request-body ceiling (#1545, item 2) - app/core/body_limit.py.

Two halves, each held separately: a declared oversize is refused before a
byte is read, and an undeclared one is cut off as it streams. Both against a
small throwaway app with a tiny ceiling, so the tests move kilobytes, and
once against the real app at its real ceiling, so the wiring and its order
relative to CORS are what is actually asserted.
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.body_limit import MAX_REQUEST_BODY_BYTES, TOO_LARGE_DETAIL, BodyLimitMiddleware, _declared_length
from app.core.photos import MAX_PHOTO_BYTES

CEILING = 64


@pytest.fixture()
def small_app():
    """An app that reads its body and reports how much arrived, behind a
    64-byte ceiling."""
    app = FastAPI()
    app.add_middleware(BodyLimitMiddleware, max_bytes=CEILING)

    @app.post("/echo-size")
    async def echo_size(request: Request) -> dict[str, int]:
        return {"received": len(await request.body())}

    return TestClient(app)


def test_a_declared_oversize_is_refused_before_the_body_is_read(small_app):
    response = small_app.post("/echo-size", content=b"x" * (CEILING + 1))

    assert response.status_code == 413
    assert response.json() == {"detail": TOO_LARGE_DETAIL}


def test_an_undeclared_oversize_is_cut_off_as_it_streams(small_app):
    # A generator body goes out chunked, with no Content-Length to check, so
    # only the running total can refuse it - the half that has to hold.
    def chunks():
        for _ in range(3):
            yield b"y" * CEILING

    response = small_app.post("/echo-size", content=chunks())

    assert response.status_code == 413
    assert response.json() == {"detail": TOO_LARGE_DETAIL}


def test_a_body_at_the_ceiling_goes_through_whole(small_app):
    response = small_app.post("/echo-size", content=b"z" * CEILING)

    assert response.status_code == 200
    assert response.json() == {"received": CEILING}


def test_an_unparseable_content_length_decides_nothing():
    # The header is a claim; a claim this cannot read is ignored and the
    # stream decides, exactly as read_capped_body treats it (#379). Asked of
    # the parser directly, because an HTTP client will not send a header it
    # knows to be malformed.
    assert _declared_length({"headers": [(b"content-length", b"not-a-number")]}) is None
    assert _declared_length({"headers": [(b"host", b"example")]}) is None
    assert _declared_length({"headers": [(b"content-length", b"12")]}) == 12


def test_a_streamed_oversize_reaches_a_real_endpoint_as_a_413(client):
    # The half that goes through FastAPI's own body parsing rather than a
    # handler reading the body itself: FastAPI turns an exception it does
    # not recognise into a 400 "error parsing the body", which is why the
    # middleware raises FastAPI's HTTPException and not Starlette's. Chunked,
    # so no Content-Length is declared and only the running total can refuse.
    def chunks():
        for _ in range(17):
            yield b" " * (1024 * 1024)

    response = client.post("/app-failures", content=chunks(), headers={"Content-Type": "application/json"})

    assert response.status_code == 413
    assert response.json() == {"detail": TOO_LARGE_DETAIL}


def test_the_real_app_refuses_past_its_ceiling_with_cors_headers(client):
    # `/app-failures` is the one write that needs no account, which makes it
    # the request an anonymous caller would choose. The Origin header is
    # what makes the response's CORS headers observable: without
    # `access-control-allow-origin` a browser reports a network error and the
    # phone never learns it sent too much - the reason app/main.py adds this
    # middleware inside CORS rather than outside it.
    response = client.post(
        "/app-failures",
        content=b"{" + b" " * MAX_REQUEST_BODY_BYTES + b"}",
        headers={"Content-Type": "application/json", "Origin": "https://ourhike.example"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": TOO_LARGE_DETAIL}
    assert response.headers["access-control-allow-origin"] == "*"


def test_the_ceiling_sits_above_the_photo_cap():
    # The photo uploads keep their own, lower cap and their own 413 wording
    # (app/routers/reports.py `_too_large`). That holds only while this
    # ceiling is the larger of the two; a ceiling below MAX_PHOTO_BYTES would
    # silently replace their message with this one.
    assert MAX_REQUEST_BODY_BYTES > MAX_PHOTO_BYTES
