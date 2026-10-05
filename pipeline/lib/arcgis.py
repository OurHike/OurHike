"""Shared fetcher for ArcGIS FeatureServer layers.

Handles pagination via resultOffset since ArcGIS servers cap how many
features they'll return per request (maxRecordCount) - and, since #1790,
halves the page when a server refuses one, because some also cap the bytes
an answer may carry and say so only by answering an error page.

Every request goes through lib/http_retry (#659): this module used to do
bare requests.get, so one transient ATC 5xx failed a whole fetch_all run -
the exact failure shape http_retry was extracted for (#536), sitting one
directory away from the module that never called it.
"""

import json
import time
from collections.abc import Callable
from pathlib import Path

import requests

from lib.http_retry import DEFAULT_BACKOFF_SECONDS, DEFAULT_RETRYABLE_STATUSES, request_with_retry

PAGE_SIZE = 1000

# A PAGE QUERY WHOSE GET URL WOULD BE LONGER THAN THIS GOES AS A POST FORM,
# the same parameters in the body (query_page()). Measured 2026-10-03 on
# services3.arcgis.com's WFIGS_Interagency_Perimeters_Current/FeatureServer/0,
# whose 118 kept fields make a 3,018-character query: a GET of 2,075
# characters answered 200, one of 2,622 answered 404, and the whole query as
# a POST answered all 113 features. 2,000 sits under the longest GET seen to
# answer. Where between 2,075 and 2,622 that host's limit lies is
# @unvalidated, and other hosts' limits are unmeasured; a shorter query is
# sent by GET exactly as before, so no layer read today changes request.
GET_URL_LIMIT = 2000

# A PAGE THAT ANSWERS 5xx IS HALVED AT ONCE, down to one feature, rather
# than retried at its size over the caller's whole backoff.
# Measured 2026-10-03 on apps.fs.usda.gov's EDW_Wilderness_02/MapServer/0
# (449 polygons): returnCountOnly answered 449 in 6.7 s, while a page of 1,000
# answered "Error performing query operation" (500) in 19 s, 250 answered 500
# in 8.7 s, and 100 answered 200 with 12,757,608 bytes in 7.2 s. Monthly run 10
# (refresh-reference.yml 37156600376) spent the monthly lane's 18-minute
# ladder retrying the page of 1,000 and failed the run.
#
# ONE FEATURE THAT STILL ANSWERS 5xx IS ASKED ONCE MORE AT
# PRECISION_FALLBACK decimal places, with the caller's whole backoff, so a
# server that is really down still gets its full wait. Measured 2026-10-04 on
# EDW_OtherNationalDesignatedArea_01/MapServer/0 (227 polygons), which monthly
# run 11 (37177022235) failed on at a page of 31: every feature answered alone
# but the one at offset 83, which answered 500 in 10.3 s, 80 bytes as Esri JSON,
# and 200 with 27,015,430 bytes at geometryPrecision=6. Six decimal places of a
# degree is at most 0.11 m, finer than a phone's GPS fix (Reasoned), and only
# that feature is rounded: the next page goes back to the last size that
# answered. A caller that sets its own geometry_precision keeps it.
PRECISION_FALLBACK = 6


def query_page(
    query_url: str,
    params: dict,
    *,
    session=None,
    backoff: tuple[int, ...] = DEFAULT_BACKOFF_SECONDS,
    retryable_statuses: tuple[int, ...] = DEFAULT_RETRYABLE_STATUSES,
):
    """One page query: a GET, or a POST form when the GET's URL would pass GET_URL_LIMIT."""
    url = requests.Request("GET", query_url, params=params).prepare().url
    method, fields = ("get", {"params": params}) if len(url) <= GET_URL_LIMIT else ("post", {"data": params})
    return request_with_retry(
        query_url, session=session, method=method, timeout=60, backoff=backoff, retryable_statuses=retryable_statuses, **fields
    )


def fetch_layer_geojson(
    layer_url: str,
    *,
    out_fields: str = "*",
    geometry_precision: int | None = None,
    page_size: int | None = None,
) -> dict:
    """Fetch every feature from an ArcGIS FeatureServer/MapServer layer as GeoJSON.

    THE STOP CONDITION IS AN EMPTY PAGE, and never a short one. A page
    shorter than what was asked for is not proof there is no more data - a
    server whose own `maxRecordCount` sits below the requested size returns
    short pages the whole way through. This loop used to stop on a short
    page and did skip data; `tests/test_lib_arcgis.py` holds both regression
    tests. The cost of getting it right is one extra request per layer that
    comes back empty, which is the correct thing to buy.

    THE QUERY SHAPE IS THE CALLER'S (#1295), because there was a second
    implementation of this loop in `publish-conditions.yml` whose only reason
    to exist was that it needed a different one - geometry only, at reduced
    precision, in bigger pages. Its stop condition trusted
    `exceededTransferLimit`, which is the early exit the tests above exist to
    prevent, so the fix was to make this function able to answer that
    caller rather than to keep two loops.

    `page_size` resolves against the module constant in the BODY rather than
    in the signature, so a test monkeypatching `arcgis.PAGE_SIZE` still
    reaches it - a default bound at definition time would have captured the
    original forever. `lib/http_retry.py`'s `sleep` argument carries the same
    note for the same reason.

    A PAGE THE SERVER REFUSES IS ASKED FOR AGAIN AT HALF THE SIZE (#1790).
    `maxRecordCount` is a count, and some servers also cap the BYTES one
    answer may carry, which no metadata states. Measured 2026-10-01 against
    the two on-prem ArcGIS Server 10.91 layers that broke every vector
    publish after #1787: PASDA's 684 DCNR trails answer a 1,000-feature page
    with a 7,058-byte HTML error page (HTTP 200), a 500-feature page as
    37.5 MB of GeoJSON in 3.6 s; CDTC's 8-feature centerline answers 1,000
    with the same HTML page and 4 features as 29.3 MB in 10 s. With `f=json`
    the same requests answer `{"error": {"code": 500, "message": "Error
    performing query operation"}}`, which is why a refusal is either an
    unparsable body or an error object. The halving repeats the SAME offset
    at the smaller size, keeps that size for the rest of the layer, and
    gives up at a page of one with the server's own words, so a layer that
    is genuinely broken still fails - after at most ten extra requests
    (1,000 halves to 1 in ten steps), which is what a wrong registration
    costs here instead of a silent skip. Whether a server refuses by count
    or by bytes is not distinguished, because it does not change what to do.
    """
    query_url = layer_url.rstrip("/") + "/query"
    features = []
    for batch in iter_layer_pages(layer_url, out_fields=out_fields, geometry_precision=geometry_precision, page_size=page_size):
        features.extend(batch)
    check_not_truncated(query_url, len(features))
    return {"type": "FeatureCollection", "features": features}


def iter_layer_pages(
    layer_url: str,
    *,
    out_fields: str = "*",
    geometry_precision: int | None = None,
    page_size: int | None = None,
    where: str = "1=1",
    session=None,
    backoff: tuple[int, ...] = DEFAULT_BACKOFF_SECONDS,
    return_z: bool = False,
    paginate: bool = True,
):
    """Yield each page of GeoJSON features `fetch_layer_geojson` would collect, in order.

    The loop itself, with every rule fetch_layer_geojson's docstring states:
    stop on an empty page and never a short one, advance by the rows the
    page returned, halve a refused page. It is a generator so the dlt
    resource in extract/_kinds.py can yield page by page through THIS loop
    rather than a second one (#1793, pipeline/ELT.md) - a second pager is
    the thing #1295 removed, and dlt's own OffsetPaginator steps by `limit`
    rather than by rows returned, which skips rows on any server whose
    `maxRecordCount` sits below the page asked for (ELT.md, "dlt
    configuration requirements": 4 of 10 rows, measured 2026-10-01).

    `where` is the entry's own filter, for a layer read only through the
    agency's status field (ELT.md, "Status layers are often stale"). The
    count that proves a short read must be taken under the same clause, so
    `layer_count` takes it too. `session` is the caller's, so a caller that
    names itself to the server (lib/user_agent.py) does so on every page.
    `backoff` is the caller's too: how long each page waits out a server that
    stops answering (lib/http_retry.py).

    A SERVER THAT IGNORES `resultOffset` IS REFUSED, not looped on. One that
    does not support pagination answers every offset with page one, and
    this loop, which stops only on an empty page, would never stop (ELT.md
    asks for a `maximum_offset` on every layer for this reason; @unvalidated
    against a live server, since none registered here has been seen doing
    it). Two consecutive pages identical feature for feature cannot come
    from one layer read in order, so the second one raises.

    `return_z` KEEPS EACH VERTEX'S ELEVATION, which `f=geojson` drops.
    Measured 2026-10-03 on ATC's Z-enabled `ATX_Ratings/FeatureServer/9`:
    `f=geojson&returnZ=true` answered 2-D coordinates, while `f=json&returnZ=true`
    answered [x, y, z] on every vertex. So with `return_z` the pages are asked
    for as Esri JSON with `returnZ=true` and converted here, by
    `esri_feature_to_geojson`, into the same GeoJSON features this loop yields
    otherwise, each coordinate carrying its Z. It is the same loop - stop on
    an empty page, advance by rows returned, halve a refused page, refuse a
    repeated one - so it is not a second pager. Off by default, and with it
    off the request is exactly what it was before (tests/test_lib_arcgis.py
    pins the whole query).

    `paginate=False` IS FOR A SERVER THAT REFUSES `resultOffset`, one whose
    layer metadata reads `advancedQueryCapabilities.supportsPagination: false`.
    Measured 2026-10-03 on cicgis.org's `Chesapeake/CAJO/MapServer/0`: a paged
    query answers `{"error": {"code": 400, "message": "Pagination is not
    supported."}}`, which this loop would halve down to a page of one and then
    fail on. That layer answers `returnIdsOnly` (843 ids under `FID`) and an
    `objectIds` query by GET and by POST alike, so `iter_pages_by_object_id`
    reads the ids once and then the features in batches of `page_size`, in
    object-id order. The caller sets `page_size` no larger than the layer's
    `maxRecordCount`; the proof of a whole read stays the caller's
    `returnCountOnly` count.
    """
    query_url = layer_url.rstrip("/") + "/query"
    records = PAGE_SIZE if page_size is None else page_size
    if not paginate:
        yield from iter_pages_by_object_id(
            query_url,
            out_fields=out_fields,
            geometry_precision=geometry_precision,
            batch_size=records,
            where=where,
            session=session,
            backoff=backoff,
            return_z=return_z,
        )
        return
    offset = 0
    previous = None
    last_good = None  # the last page size that answered, to go back to after one rounded feature
    rounded = False  # this one feature is being asked at PRECISION_FALLBACK
    while True:
        params = {
            "where": where,
            "outFields": out_fields,
            "outSR": 4326,
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": records,
        }
        if return_z:
            params["f"] = "json"
            params["returnZ"] = "true"
        if geometry_precision is not None:
            params["geometryPrecision"] = geometry_precision
        elif rounded:
            params["geometryPrecision"] = PRECISION_FALLBACK
        # A 5xx is not retried at a size it can be halved from, nor before the rounded ask; that
        # last ask gets the caller's whole backoff. A timeout keeps the backoff at every size: a
        # stalled server, as DEC's was on 2026-10-03, hung its count query too.
        last_chance = rounded or (records <= 1 and geometry_precision is not None)
        statuses = DEFAULT_RETRYABLE_STATUSES if last_chance else (429,)
        try:
            resp = ask_until_let_in(
                lambda: query_page(query_url, params, session=session, backoff=backoff, retryable_statuses=statuses),
                query_url,
            )
        except requests.HTTPError as failure:
            status = failure.response.status_code if failure.response is not None else None
            if last_chance or status is None or status < 500:
                raise
            if records > 1:
                smaller = records // 2
                print(f"  {query_url} answered {status} at a page of {records}; retrying at {smaller}")
                records = smaller
            else:
                print(
                    f"  {query_url} answered {status} for the feature at offset {offset}; asking it at {PRECISION_FALLBACK} decimals"
                )
                rounded = True
            continue
        refusal = page_refusal(resp)
        if refusal is not None:
            if records <= 1:
                raise RuntimeError(f"{query_url} {refusal} at a page of 1 feature")
            smaller = records // 2
            print(f"  {query_url} {refusal} at a page of {records}; retrying at {smaller}")
            records = smaller
            continue
        batch = resp.json().get("features", [])
        if return_z:
            batch = [esri_feature_to_geojson(feature) for feature in batch]
        if not batch:
            return
        if batch == previous:
            raise RuntimeError(f"{query_url} answered offset {offset} with the page before it; it ignores resultOffset")
        yield batch
        previous = batch
        offset += len(batch)
        if rounded:
            rounded = False
            records = last_good or records
        else:
            last_good = records


def feature_object_id(feature: dict, oid_field: str | None):
    """A page's feature's object id, or None where it carries none: GeoJSON's `id`, else the id field's value."""
    if feature.get("id") is not None:
        return feature["id"]
    properties = feature.get("properties") or {}
    return properties.get(oid_field) if oid_field else None


def iter_pages_by_object_id(
    query_url: str,
    *,
    out_fields: str = "*",
    geometry_precision: int | None = None,
    batch_size: int = PAGE_SIZE,
    where: str = "1=1",
    session=None,
    backoff: tuple[int, ...] = DEFAULT_BACKOFF_SECONDS,
    return_z: bool = False,
):
    """Yield a non-paginating layer's features in pages, by object id: iter_layer_pages' `paginate=False` path.

    One `returnIdsOnly` query under `where`, then the ids in ascending order,
    `batch_size` at a time, each batch POSTed as `objectIds`. POST, because a
    thousand ids are several kilobytes of URL, past the 2,048-byte query
    string IIS allows by default (Reasoned from IIS's documented default; the
    measured layer answered GET and POST the same for 3 ids). A batch the
    server refuses is asked for again at half the size, as a refused page is.
    A server that answers a batch with features whose ids it was not asked
    for is ignoring `objectIds` and is refused, rather than read as the
    layer. An empty id list is an empty layer; whether it is a whole one is
    the caller's `returnCountOnly` check, as for the paged loop.
    """
    answer = ask_until_let_in(
        lambda: request_with_retry(
            query_url,
            session=session,
            params={"where": where, "returnIdsOnly": "true", "f": "json"},
            timeout=60,
            backoff=backoff,
        ),
        query_url,
    )
    refusal = page_refusal(answer)
    if refusal is not None:
        raise RuntimeError(f"{query_url} {refusal} when asked for its object ids")
    body = answer.json()
    oid_field = body.get("objectIdFieldName")
    ids = sorted(body.get("objectIds") or [])
    size = batch_size
    index = 0
    while index < len(ids):
        batch = ids[index : index + size]
        form = {"objectIds": ",".join(str(oid) for oid in batch), "outFields": out_fields, "outSR": 4326, "f": "geojson"}
        if return_z:
            form["f"] = "json"
            form["returnZ"] = "true"
        if geometry_precision is not None:
            form["geometryPrecision"] = geometry_precision
        resp = ask_until_let_in(
            lambda: request_with_retry(query_url, session=session, method="post", data=form, timeout=60, backoff=backoff),
            query_url,
        )
        refusal = page_refusal(resp)
        if refusal is not None:
            if size <= 1:
                raise RuntimeError(f"{query_url} {refusal} for 1 object id")
            print(f"  {query_url} {refusal} for {size} object ids; retrying at {size // 2}")
            size //= 2
            continue
        features = resp.json().get("features", [])
        if return_z:
            features = [esri_feature_to_geojson(feature) for feature in features]
        asked = set(batch)
        stray = [oid for oid in (feature_object_id(f, oid_field) for f in features) if oid is not None and oid not in asked]
        if stray:
            raise RuntimeError(f"{query_url} answered object ids it was not asked for ({stray[:3]}); it ignores objectIds")
        yield features
        index += len(batch)


def esri_geometry_to_geojson(geometry: dict | None) -> dict | None:
    """One Esri JSON geometry as a GeoJSON geometry, every coordinate kept as the server sent it, Z included.

    Points, multipoints and polylines, which is every Z-enabled layer
    registered so far: a polyline of one path is a LineString and of several
    a MultiLineString, as `f=geojson` answers them. An empty geometry is None,
    GeoJSON's null geometry. A POLYGON RAISES: Esri rings are told apart as
    outer or hole by their winding and must be regrouped, which this does not
    do yet, and a polygon read wrong is worse than one not read. A Z-enabled
    polygon layer is read without `return_z` until somebody builds that.
    """
    if not geometry:
        return None
    if "x" in geometry:
        if geometry.get("x") is None or geometry.get("x") == "NaN":
            return None
        coordinates = [geometry["x"], geometry["y"]]
        if geometry.get("z") is not None:
            coordinates.append(geometry["z"])
        return {"type": "Point", "coordinates": coordinates}
    if "points" in geometry:
        return {"type": "MultiPoint", "coordinates": geometry["points"]} if geometry["points"] else None
    if "paths" in geometry:
        paths = [path for path in geometry["paths"] if path]
        if not paths:
            return None
        if len(paths) == 1:
            return {"type": "LineString", "coordinates": paths[0]}
        return {"type": "MultiLineString", "coordinates": paths}
    if "rings" in geometry:
        raise ValueError("an Esri polygon is not converted with its Z yet; read this layer without return_z")
    raise ValueError(f"an Esri geometry of no known shape: {sorted(geometry)}")


def esri_feature_to_geojson(feature: dict) -> dict:
    """One Esri JSON feature as the GeoJSON feature `f=geojson` would have answered, its Z kept."""
    return {
        "type": "Feature",
        "properties": feature.get("attributes") or {},
        "geometry": esri_geometry_to_geojson(feature.get("geometry")),
    }


def check_not_truncated(query_url: str, fetched: int) -> None:
    """Raise when the server says the layer holds more features than were fetched (#1730).

    The loop above stops on an empty page, which a server can also answer
    in place of an error part-way through a layer - the file is then
    written short and `fetch_all` records the layer as up to date, so no
    later run fetches it again. One `returnCountOnly=true` query after the
    loop is the cheap cross-check: a server that holds 4,395 features and
    handed over 3,000 is a failed fetch, not a small layer.

    ONE DIRECTION ONLY. Fewer fetched than counted raises. More fetched
    than counted does not: a layer edited between the count and the pages
    can move either way, and an overshoot loses nothing. A count that
    cannot be read (an error object, a non-JSON body, no `count` key, a
    refused request) is printed and skipped, never treated as a pass or a
    fail - whether every server this repo fetches from supports
    `returnCountOnly` is unmeasured, and failing the fetch on that would
    turn a missing capability into an outage. @unvalidated: the support
    is asserted by the ArcGIS REST spec, not checked per registered source.
    """
    count = layer_count(query_url)
    if count is not None and fetched < count:
        raise RuntimeError(f"{query_url} holds {count} features but {fetched} were fetched; the layer was truncated")


def layer_count(
    query_url: str, *, where: str = "1=1", session=None, backoff: tuple[int, ...] = DEFAULT_BACKOFF_SECONDS
) -> int | None:
    """The server's own `returnCountOnly` count for `where`, or None when it cannot be read.

    Split out of check_not_truncated so the extract run check can record
    the count as the proof an empty or short table needs (pipeline/ELT.md,
    "A full reload that cannot empty a safety table"). None is printed with
    its reason and is never a count of zero: an allowed-empty closures layer
    without a readable count is UNKNOWN there, not a quiet trail.
    """
    try:
        resp = request_with_retry(
            query_url,
            session=session,
            params={"where": where, "returnCountOnly": "true", "f": "json"},
            timeout=60,
            backoff=backoff,
        )
        count = resp.json().get("count")
    except (ValueError, AttributeError, requests.RequestException) as exc:
        print(f"  {query_url} count check skipped: {exc}")
        return None
    if not isinstance(count, int):
        print(f"  {query_url} count check skipped: no integer count in the answer")
        return None
    return count


#: ArcGIS Online answers a rate-limited query with HTTP 200 and a JSON error object of code 429, "Unable to perform
#: query. Too many requests." Oregon Metro's trails on services2.arcgis.com did so in monthly run 14
#: (refresh-reference.yml 37207306294, 2026-10-04), and the paged loop read it as a page too large and halved down to
#: one feature before giving up, which stopped the whole monthly extract. A throttled answer is never halved: the same
#: request is made again after each wait here, and only after the last one does the read fail. @unvalidated: Esri
#: publishes no figure for how long an anonymous client is held back, so the 7.5 minutes this ladder waits in all is a
#: guess. The next throttled run's log, which names every wait, would settle it.
THROTTLE_WAITS_SECONDS = (30, 60, 120, 240)


def is_throttled(resp) -> bool:
    """Whether this answer is ArcGIS's rate limit, an error object of code 429 in the body, whatever the HTTP status."""
    try:
        body = resp.json()
    except ValueError:
        return False
    error = body.get("error") if isinstance(body, dict) else None
    return bool(error) and str(error.get("code")) == "429"


def ask_until_let_in(ask: Callable[[], requests.Response], what: str) -> requests.Response:
    """`ask()`'s answer, asked again after each of THROTTLE_WAITS_SECONDS while it is throttled (is_throttled).

    Raises RuntimeError, naming the server's words, when the last wait is spent and the answer is still the rate
    limit, so a caller never halves a page or reads a refusal as an answer."""
    for wait in (*THROTTLE_WAITS_SECONDS, None):
        resp = ask()
        if not is_throttled(resp):
            return resp
        if wait is None:
            raise RuntimeError(f"{what} {page_refusal(resp)} after {len(THROTTLE_WAITS_SECONDS)} waits for its rate limit")
        print(f"  {what} answered its rate limit (429 in the body); asking again in {wait} s")
        time.sleep(wait)
    raise AssertionError("unreachable")


def page_refusal(resp) -> str | None:
    """Why this answer is not a page of features, or None when it is one.

    Two shapes, both seen from the same servers on 2026-10-01 (see
    fetch_layer_geojson): a body that is not JSON at all - an HTML error
    page sent with HTTP 200, which `request_with_retry` cannot tell from a
    good answer - and a JSON error object in place of a feature collection.
    A collection with no `features` key is NOT a refusal: that is a server
    saying "nothing here", and the caller's stop condition owns it.
    """
    try:
        body = resp.json()
    except ValueError:
        return f"answered {resp.headers.get('content-type', 'no content type')} rather than JSON"
    error = body.get("error") if isinstance(body, dict) else None
    if error:
        return f"answered error {error.get('code')}: {error.get('message')}"
    return None


def fetch_layer_to_file(
    layer_url: str,
    out_path: Path,
    *,
    out_fields: str = "*",
    geometry_precision: int | None = None,
    page_size: int | None = None,
) -> int:
    """Fetch a layer and write it to out_path as GeoJSON. Returns feature count."""
    fc = fetch_layer_geojson(
        layer_url,
        out_fields=out_fields,
        geometry_precision=geometry_precision,
        page_size=page_size,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fc))
    return len(fc["features"])


def get_layer_edit_date(layer_url: str) -> int | None:
    """Fetch a layer's dataLastEditDate (epoch ms) - a cheap metadata-only
    request, used to skip re-fetching layers that haven't changed. Returns
    None if the service doesn't expose editingInfo (some don't)."""
    resp = request_with_retry(layer_url, params={"f": "json"}, timeout=30)
    editing_info = resp.json().get("editingInfo")
    if not editing_info:
        return None
    return editing_info.get("dataLastEditDate")


def get_field_coded_domain(layer_url: str, field_name: str) -> dict[int, str] | None:
    """Fetch a layer's field metadata and return field_name's coded-value
    domain as a {code: label} dict - e.g. side_trails' `Blaze` field, so its
    0-9 color codes are decoded from the service's own metadata rather than
    hand-copied (see features/TRAIL_BLAZE_COLORS.md). Returns None if the
    field isn't found, has no domain, or has a non-coded domain (e.g. a
    numeric range domain)."""
    resp = request_with_retry(layer_url, params={"f": "json"}, timeout=30)
    fields = resp.json().get("fields", [])
    for field in fields:
        if field.get("name") == field_name:
            domain = field.get("domain")
            if domain and domain.get("type") == "codedValue":
                return {cv["code"]: cv["name"] for cv in domain.get("codedValues", [])}
            return None
    return None


def get_layer_max_field(layer_url: str, field_name: str) -> str | None:
    """The layer's `max(field_name)`, as one statistics query, or None.

    The substitute change marker for a layer whose server exposes no
    `editingInfo` (#1311). An on-prem ArcGIS server - NYS DEC's, the Forest
    Service's - answers `get_layer_edit_date` with None, and until this
    existed that meant the layer was re-fetched on every run: 21,470
    back-country features for DEC alone, unchanged since 2026-08-18 by the
    field this reads. `sources.json` records the field per entry as
    `freshness.kind: arcgis_max_field`, with the measurement that chose it.

    Returned as a STRING, whatever the server's type, because the value is
    only ever compared verbatim against the one recorded on the last fetch -
    the same rule lib/freshness_state.compare_marker keeps for every other
    marker, so an epoch-millisecond integer and its JSON round-trip cannot
    manufacture a change.

    None when the server returns no statistics row, which the caller reads
    as "no marker" and fetches. Never rounded to "unchanged".
    """
    query_url = layer_url.rstrip("/") + "/query"
    statistics = [{"statisticType": "max", "onStatisticField": field_name, "outStatisticFieldName": "marker"}]
    params = {"where": "1=1", "outStatistics": json.dumps(statistics), "f": "json"}
    resp = request_with_retry(query_url, params=params, timeout=30)
    features = resp.json().get("features") or []
    if not features:
        return None
    value = (features[0].get("attributes") or {}).get("marker")
    return None if value is None else str(value)


def get_service_etag(url: str) -> str | None:
    """The ETag a HEAD on `url` answers with, or None if it answers none.

    The other substitute marker (#1311): the Forest Service's EDW server has
    no `editingInfo` AND no date column, so the only thing that can move
    when its data does is the ETag on the service description document.
    `sources.json` tags that as @unvalidated - an ETag on the METADATA has
    not been shown to move when the FEATURES do - which is why the caller
    records both sides of every comparison rather than trusting this alone.

    Compared verbatim, weak validators included: the question is only
    "did it move", exactly as check_freshness.py asks ATC's feed.
    """
    resp = request_with_retry(url, method="head", timeout=30)
    return resp.headers.get("ETag")
