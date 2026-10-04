"""Retrying a request against a third-party host that is having a moment.

THE FAILURE THAT PROMPTED THIS (#536)

A full publish - photos, elevation, the lot - died 35 seconds in on:

    504 Server Error: Gateway Timeout for url:
    https://tnmaccess.nationalmap.gov/api/v1/products?bbox=-84.72...

That was the FIRST of 51 corridor cells. `fetch_elevation.py` asked USGS's
catalogue once per cell with no retry, so a single transient gateway timeout
from somebody else's server threw away the whole run - including the work
already done by every step before it. The same endpoint answered 200 an hour
earlier and an hour later; it flaked, and nothing absorbed it.

WHY THIS IS A MODULE RATHER THAN A FOURTH COPY

Three fetchers had already written this loop by hand - `fetch_poi_images.py`,
`fetch_atc_photos.py` and `fetch_topo_quads.py` - and the one that had not is
the one that broke. That is the "one home per item" rule failing in the
direction it usually fails: the idiom spread by copying, and the file that
missed out was invisible until it cost an hour of build.

THE POSTURES ARE DELIBERATELY DIFFERENT, SO POLICY IS THE CALLER'S

This does not unify what those scripts decided. `fetch_topo_quads.py` retries
connection faults ONLY, and says why in as many words: it persists each quad
as it lands, so a mid-run failure loses almost nothing. `fetch_poi_images.py`
retries 429 and 5xx too, because an aborted crawl loses every un-flushed
outcome. Both are right about themselves.

So `retryable_statuses` and `backoff` are parameters. What is shared is the
mechanism - when to sleep, how long, whether to honour `Retry-After`, and
raising loudly once the budget is spent. What stays local is how patient a
given caller should be.
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

from lib.user_agent import USER_AGENT

# A pause ladder. One entry per retry, so `(5, 30)` means three attempts.
DEFAULT_BACKOFF_SECONDS = (5, 30)

# Answers that mean "ask again", as opposed to an answer. 429 is explicit
# rate limiting; the 5xx family is the server failing rather than refusing.
# A 4xx that is not 429 is the host saying no, and asking twice will not
# change its mind - so it raises immediately rather than spending the budget.
DEFAULT_RETRYABLE_STATUSES = (429, 500, 502, 503, 504)

# A server-sent `Retry-After` wins over the local ladder, but capped: an
# errant header must not park a build for an hour.
MAX_RETRY_AFTER_SECONDS = 120

# The faults that are worth another go. A timeout here is OUR client giving
# up on a slow response, which is exactly the case where trying again works.
TRANSIENT_EXCEPTIONS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.Timeout,
)


def named(headers: dict | None, session: requests.Session | None = None) -> dict | None:
    """`headers`, plus lib/user_agent.py's `USER_AGENT` when nothing else names the caller.

    THE GAP THIS CLOSES. With no session, both functions below fell through
    to bare `requests`, which sends `python-requests/<version>`. Read
    2026-10-02: `fetch_external_layers.py`, the fetch behind every network
    trail source, reaches `request_with_retry` that way through
    `lib/arcgis.py`, and so do `fetch_centerline.py`, `export_trails.py`
    and `export_spurs.py`, while `lib/user_agent.py` says the string goes to
    every host. That module's measurement is why this is not courtesy:
    ATC's site answered the default agent 403 and this string 200.

    A session on requests' default agent gets it too: `export_dem.py`
    builds a bare `requests.Session()` for its tile fetches (read the same
    day), while the other fetchers' sessions set `USER_AGENT` themselves.

    The caller's own choice always wins. An agent in `headers`, matched
    without regard to case as HTTP does, is left alone, and so is any agent
    a session already carries, which keeps the photo fetchers'
    `CONTACTABLE_USER_AGENT`.
    """
    if any(key.lower() == "user-agent" for key in headers or {}):
        return headers
    carried = getattr(session, "headers", {}).get("User-Agent") if session is not None else None
    if carried and carried != requests.utils.default_user_agent():
        return headers
    return {**(headers or {}), "User-Agent": USER_AGENT}


def retry_after_seconds(response: requests.Response) -> int | None:
    """The integer `Retry-After` a 429/503 carries, capped.

    None when the header is absent or in the HTTP-date form, which is rare
    enough that the local ladder is a fine substitute for parsing it.
    """
    header = response.headers.get("Retry-After", "")
    if not header.isdigit():
        return None
    return min(int(header), MAX_RETRY_AFTER_SECONDS)


def request_with_retry(
    url: str,
    *,
    session: requests.Session | None = None,
    method: str = "get",
    params: dict | None = None,
    data: dict | None = None,
    timeout: int = 60,
    backoff: tuple[int, ...] = DEFAULT_BACKOFF_SECONDS,
    retryable_statuses: tuple[int, ...] = DEFAULT_RETRYABLE_STATUSES,
    throttle_seconds: float = 0.0,
    label: str | None = None,
    headers: dict | None = None,
    sleep=None,
) -> requests.Response:
    """One request, retried over `backoff` on transient faults and statuses.

    `data` is the form body a POST carries, for the one caller that signs in
    rather than reads: fetch_hikefinder.py posts the export's site password
    (#1468). It rides every attempt unchanged, like `headers`. NOTHING HERE
    PRINTS IT - the retry lines carry `label` and the exception type, never
    the body - and a caller sending a secret should keep it out of `label`
    and out of the URL for the same reason.

    `headers` rides every attempt unchanged, the same as download_with_retry's
    and for a third caller (#1288): fetch_nynjtc_long_path_guide.py sends
    If-None-Match / If-Modified-Since per page, which a session-wide header
    cannot carry because they differ per URL.

    Raises the underlying exception, or `raise_for_status()`, once the budget
    is spent - a run that quietly proceeded on a failed fetch would be worse
    than one that stops, because the artifact it went on to build would be
    wrong rather than absent.

    `sleep` is injected so a test can assert the ladder without waiting it
    out; nothing else should pass it. The None sentinel resolves to
    time.sleep in the body rather than in the signature, so a caller's test
    can also monkeypatch this module's time.sleep - a default bound at
    definition time would have captured the real one forever.
    """
    if sleep is None:
        sleep = time.sleep
    requester = session or requests
    attempts = len(backoff) + 1
    name = label or url

    for attempt, delay in enumerate((*backoff, None)):
        try:
            response = requester.request(method, url, params=params, data=data, timeout=timeout, headers=named(headers, session))
        except TRANSIENT_EXCEPTIONS as error:
            if delay is None:
                raise
            print(f"  {name}: {type(error).__name__} on attempt {attempt + 1}/{attempts}, retrying in {delay}s")
            sleep(delay)
            continue

        if response.status_code in retryable_statuses and delay is not None:
            wait = retry_after_seconds(response) or delay
            print(f"  {name} answered {response.status_code} on attempt {attempt + 1}/{attempts}, retrying in {wait}s")
            sleep(wait)
            continue

        # Out of retries, or a status that is an answer rather than a flake.
        response.raise_for_status()
        if throttle_seconds:
            sleep(throttle_seconds)
        return response

    raise AssertionError("unreachable")


def download_with_retry(
    url: str,
    dest: Path,
    *,
    timeout: int = 600,
    backoff: tuple[int, ...] = DEFAULT_BACKOFF_SECONDS,
    retryable_statuses: tuple[int, ...] = DEFAULT_RETRYABLE_STATUSES,
    headers: dict | None = None,
    chunk_bytes: int = 1 << 20,
    label: str | None = None,
    sleep=None,
    response_headers: dict | None = None,
) -> Path:
    """Stream a large file to `dest`, retrying the WHOLE transfer.

    `response_headers`, when given, is filled with the headers of the one
    response whose body became `dest`, for the third caller (#1652):
    extract/_geofabrik.py records each extract's Last-Modified and ETag in
    its manifest and holds the file's size to that response's
    Content-Length, which a second HEAD could not promise to describe the
    same bytes.

    `headers` rides every attempt unchanged. It exists for the second caller
    (#1066): fetch_trail_water.py's NHD downloads identify themselves with a
    User-Agent, and moving them onto this retry must not cost USGS that
    courtesy.

    THE FAULT THIS EXISTS FOR (#1063): a 600-second read timeout against
    download.geofabrik.de, ten minutes into a 3.5 GB state extract, which
    ended a production publish at step 15 of 39 with nothing uploaded
    (run 33005545820). Being precise about where it landed, because it
    decides how much of this function is measurement and how much is
    design: the traceback carries no `iter_content` frame - it came out of
    `requests.get` itself, via `adapters.send`. So that ONE failure would
    have been survived by retrying the request alone.

    WHY THE RETRY UNIT IS THE TRANSFER ANYWAY, which is the part that is
    reasoned rather than measured. `request_with_retry` has no streaming
    path at all - it reads the whole body into memory, which 3.5 GB may not
    do - and a streamed body can also fault mid-iteration, minutes after
    the headers arrived, where a request-only retry has already returned
    and cannot help. Retrying the whole transfer covers both, and the only
    thing it costs is re-pulling bytes that had already landed. The
    mid-body case is tested rather than assumed; see
    tests/test_http_retry.py.

    NO RANGE RESUME, which is the obvious next thought and is deliberately
    not here. Resuming would turn a retry from "re-pull this file" into
    "finish this file", and it depends on the server honouring `Range` AND
    on noticing when it silently does not - a server that ignores the header
    and replays from byte zero appends a second copy onto the first, and the
    result is a corrupt archive that looks like a complete one. A slow retry
    is a worse trade than a fast one and a better trade than that. What
    would settle it: a `HEAD` establishing `Accept-Ranges`, plus a length
    check against `Content-Length` before the rename.

    `dest` IS NEVER HALF-WRITTEN. Bytes land in a sibling `.part` and are
    renamed into place only once the body is complete, so a caller's
    `dest.exists()` skip - which is how fetch_states avoids re-pulling the
    states it already has - can never be satisfied by a truncated file. The
    `.part` is removed on the way out whether or not the transfer worked,
    which the hand-written loop this replaces did not do.
    """
    if sleep is None:
        sleep = time.sleep
    attempts = len(backoff) + 1
    name = label or url
    part = dest.with_name(dest.name + ".part")

    try:
        for attempt, delay in enumerate((*backoff, None)):
            try:
                with requests.get(url, stream=True, timeout=timeout, headers=named(headers)) as response:
                    if response.status_code in retryable_statuses and delay is not None:
                        wait = retry_after_seconds(response) or delay
                        print(
                            f"  {name} answered {response.status_code} on attempt {attempt + 1}/{attempts}, retrying in {wait}s"
                        )
                        sleep(wait)
                        continue
                    response.raise_for_status()
                    # Truncates rather than appends, so a retry after a
                    # part-written attempt starts from an empty file.
                    with open(part, "wb") as handle:
                        for chunk in response.iter_content(chunk_size=chunk_bytes):
                            handle.write(chunk)
            except TRANSIENT_EXCEPTIONS as error:
                if delay is None:
                    raise
                print(f"  {name}: {type(error).__name__} on attempt {attempt + 1}/{attempts}, retrying in {delay}s")
                sleep(delay)
                continue

            part.replace(dest)
            if response_headers is not None:
                response_headers.clear()
                response_headers.update(response.headers)
            return dest
    finally:
        part.unlink(missing_ok=True)

    raise AssertionError("unreachable")
