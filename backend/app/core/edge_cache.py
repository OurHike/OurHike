"""Which responses a shared cache in front of this API may keep, and for how long.

backend/HOSTING.md is the decision (2026-10-23): the API is served at
`api.ourhike.org` through Cloudflare's proxy, and three of the four anonymous
reads every hiker's app makes on every open are cached at the edge. Uncached,
those reads reach this process once per hiker. The cost model behind the plan
for #600 (standing up the production backend) put the point where they use up
Render's and Supabase's free 5 GB a month at about 2,750 hikers. That figure is
reasoned from usage inputs nobody has measured; the 5 GB limits are the
vendors' own, read 2026-10-23. The fourth read, `GET /field-notes`, is #1905.

**THREE ROUTES, NAMED, AND NO OTHERS.** `GET /closures`, `GET /reports` and
`GET /disputes`. Each answers every anonymous caller with the same bytes and
carries no signed URL: a report's photos are fetched through their own
`no-store` redirect, never embedded. `GET /field-notes` and
`GET /waypoints/{poi_id}/photos` are left out on purpose. Both embed presigned
photo URLs that expire `PHOTO_URL_TTL_SECONDS` after signing, and
app/core/photos.py says why a shared copy of one must not exist: it "would
outlive both the signature and the visibility decision behind it".
tests/test_edge_cache.py lists the three, so adding a fourth is a visible
decision rather than a decorator copied from a neighbour.

**A SIGNED-IN CALLER IS NEVER SHARED.** A request carrying `Authorization`
gets `private, no-store`, whatever the route does with the token. Cloudflare
does not store a response marked private, so a reporter's view of their own
report waiting in the queue cannot be handed to the next caller.

**A SHARED COPY CARRIES ITS OWN CORS ANSWER.** Starlette's CORSMiddleware adds
`Access-Control-Allow-Origin` only when the request sent an `Origin` header,
and the edge keys its copy on the URL, not on the Origin. A copy filled by
curl, a monitor or a crawler would otherwise reach every browser for the next
`EDGE_TTL_SECONDS` without the header, and every browser would refuse to read
it. That is #427's failure (the data bucket's allow-list missing production for
eight days), one layer up. Setting `*` here repeats what `allow_origins=["*"]`
in app/main.py already answers any browser. If CORS is ever narrowed from `*`,
one origin's answer can no longer be shared, and these routes have to leave
the edge cache in the same change.

**EVERYTHING ELSE SAYS `no-store`** (NoStoreByDefaultMiddleware). A cache rule
set up more generously than LAUNCH_CHECKLIST.md §6 asks for then still cannot
keep a response that carries a signed URL or somebody's own data.
"""

from __future__ import annotations

from fastapi import Request, Response
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# How long the edge may serve its copy before asking this process again.
#
# Reasoned, not measured. The maintainer's tolerance for a closure is a day
# ("a closure can be latent by a day", 2026-08-08, features/CONDITIONS_DELIVERY.md),
# and the published baseline already lands about every 4 hours (#1316, GitHub's
# scheduler measured over 40 runs).
# Five minutes adds at most 300 s to a closure a moderator has just verified,
# and keeps a lifted closure drawn for at most 300 s longer, which is the
# cautious direction. Any value well under the bake's 4 hours would sit inside
# the tolerance; 300 is the pick. It also sets the cost: this process sees at
# most one request per URL per edge location per 300 s, however many hikers ask.
EDGE_TTL_SECONDS = 300

# `max-age=0` keeps the phone's own HTTP cache out of it. The hourly refresh in
# client/src/lib/useConditions.ts expects the freshest answer the network has,
# and a browser copy on top of the edge's would stack two ages.
SHARED = f"public, max-age=0, s-maxage={EDGE_TTL_SECONDS}"
PRIVATE = "private, no-store"
NO_STORE = "no-store"


def shared_at_edge(request: Request, response: Response) -> None:
    """Route dependency: let the edge keep this answer, unless the caller signed in.

    Headers set here reach a normal return only. An error the route raises is
    answered without them and falls through to NoStoreByDefaultMiddleware, so
    a 500 or a 503 is never kept for five minutes in front of every hiker.
    """
    if "authorization" in request.headers:
        response.headers["Cache-Control"] = PRIVATE
        return
    response.headers["Cache-Control"] = SHARED
    response.headers["Access-Control-Allow-Origin"] = "*"


class NoStoreByDefaultMiddleware:
    """Mark every response `no-store` unless its route already chose a policy.

    Never overwrites: the photo redirects' `private, no-store, max-age=0`
    (app/routers/reports.py) and `shared_at_edge`'s answers pass through as set.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_default(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if "cache-control" not in headers:
                    headers["Cache-Control"] = NO_STORE
            await send(message)

        await self.app(scope, receive, send_with_default)
