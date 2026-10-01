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
from pathlib import Path

import requests

from lib.http_retry import request_with_retry

PAGE_SIZE = 1000


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

    A SERVER THAT IGNORES `resultOffset` IS REFUSED, not looped on. One that
    does not support pagination answers every offset with page one, and
    this loop, which stops only on an empty page, would never stop (ELT.md
    asks for a `maximum_offset` on every layer for this reason; @unvalidated
    against a live server, since none registered here has been seen doing
    it). Two consecutive pages identical feature for feature cannot come
    from one layer read in order, so the second one raises.
    """
    query_url = layer_url.rstrip("/") + "/query"
    records = PAGE_SIZE if page_size is None else page_size
    offset = 0
    previous = None
    while True:
        params = {
            "where": where,
            "outFields": out_fields,
            "outSR": 4326,
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": records,
        }
        if geometry_precision is not None:
            params["geometryPrecision"] = geometry_precision
        resp = request_with_retry(query_url, session=session, params=params, timeout=60)
        refusal = page_refusal(resp)
        if refusal is not None:
            if records <= 1:
                raise RuntimeError(f"{query_url} {refusal} at a page of 1 feature")
            smaller = records // 2
            print(f"  {query_url} {refusal} at a page of {records}; retrying at {smaller}")
            records = smaller
            continue
        batch = resp.json().get("features", [])
        if not batch:
            return
        if batch == previous:
            raise RuntimeError(f"{query_url} answered offset {offset} with the page before it; it ignores resultOffset")
        yield batch
        previous = batch
        offset += len(batch)


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


def layer_count(query_url: str, *, where: str = "1=1", session=None) -> int | None:
    """The server's own `returnCountOnly` count for `where`, or None when it cannot be read.

    Split out of check_not_truncated so the extract run check can record
    the count as the proof an empty or short table needs (pipeline/ELT.md,
    "A full reload that cannot empty a safety table"). None is printed with
    its reason and is never a count of zero: an allowed-empty closures layer
    without a readable count is UNKNOWN there, not a quiet trail.
    """
    try:
        resp = request_with_retry(
            query_url, session=session, params={"where": where, "returnCountOnly": "true", "f": "json"}, timeout=60
        )
        count = resp.json().get("count")
    except (ValueError, AttributeError, requests.RequestException) as exc:
        print(f"  {query_url} count check skipped: {exc}")
        return None
    if not isinstance(count, int):
        print(f"  {query_url} count check skipped: no integer count in the answer")
        return None
    return count


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
