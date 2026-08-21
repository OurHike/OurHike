"""Report photos, stored in Cloudflare R2 and keyed by the report they belong to.

See ../../../features/REPORT_A_PROBLEM.md ("v1 is just a note and an optional
photo") and issue #234, which decided R2 over Supabase Storage on **egress**:
R2 does not charge for it, and photos are the payload that makes egress grow.

R2 is not a new vendor here. `pipeline/publish.py` already syncs published
artifacts to it over boto3's S3-compatible API, reading the same four
environment variables and gating writes behind an explicit flag. This reuses
that pattern rather than inventing a second one - including the write gate,
which exists so that a process which should not upload cannot.

WHY THE KEY IS DERIVED FROM THE REPORT ID AND NEVER STORED SEPARATELY

`reports/{report_id}/{n}.jpg`, computed - not a random key written into a
column and looked up. Two stores with no transaction between them drift, and
the derived key is what decides whether that drift is a bookkeeping problem or
a structural one. It answers the two questions that would otherwise need a
database: *which objects belong to this report* (from the id alone) and *does
this object still have a report* (by parsing the key). Reconciliation becomes
a set difference between `SELECT id FROM reports` and `ListObjectsV2` - a cron
job rather than a design problem - and a retry overwrites the same key instead
of duplicating it, which matters because on this trail a request that fails
after committing is the normal case rather than the edge one.

**The direction of truth, stated once so it is not re-litigated per bug: the
report row is authoritative, the R2 object is derived and disposable.** Never
the reverse. A missing object degrades to "no photo"; an orphaned object gets
swept.

WHY THE BUCKET IS PRIVATE

The original framing was that report photos are public anyway. That is not
uniformly true and the exceptions are the ones that matter: `bad_hikers` is
`internal_only` and those are photos *of people*; `thanks` is `club_only`; and
even for the six public types a photo is attached at CREATE time, before
moderation, which #229 established is not publicly visible. A public-read
bucket would reopen that hole one layer down.

So objects are written private, and reading them goes through an authorising
path that checks the owning report's own `visibility` and `status` first -
`GET /reports/{id}/photo` in app/routers/reports.py, which answers with a
redirect to a short-lived signed URL rather than the bytes.

There are two spellings of that answer and one check behind them (#385).
`/photo` redirects, for anything that can follow a hop. `/photo/link` returns
the URL as JSON, for the caller that cannot: an `<img>` carries no
`Authorization` header, so an anonymous request gets the public answer - a
404 for the `internal_only` photo, rendering as a broken image the moderation
queue could not tell from a report with no photo. Both go through
`_authorised_photo_url`, because a second copy of the check is a second place
for the rule about photos of people to drift.

WHY A SIGNED URL AND NOT A WORKER, WHICH IS A DEPARTURE FROM #234

#234 specified a Cloudflare Worker in front of the bucket. The property it was
bought for is real - the object is unreachable until something checks the
report - and that property is kept here. What changed is where the check runs,
for one reason: **the check needs the report row, and the report row is in
Postgres behind this backend.** A Worker would have had to either reach the
database from Cloudflare's edge (a new production dependency) or call back to
this backend per image - in which case the backend is in the authorising path
anyway and the Worker is a second runtime, a second deploy, and a second copy
of `_visible_to` written in another language. That rule has drifted once
already when it existed in two places (see the note on `_visible_to`), and it
is the rule that decides whether a photo of a person is readable.

So the check stays in the one place that already holds it, and the bytes still
never pass through this backend: the response is a 302 to a presigned R2 URL,
and R2 serves the object directly. Egress stays free, which is the reason R2
was chosen at all.

**The cost, named rather than discovered later.** A signed URL is a bearer
token for one object: whoever holds it can fetch it until it expires, with no
further check. A Worker re-checking per request would not have that property.
That is why the TTL below is minutes rather than hours, why the redirect is
`no-store` (a cached redirect would outlive both the signature and the
visibility decision behind it), and why this is written down - if the exposure
ever matters more than the second runtime costs, the endpoint's contract does
not change when a Worker replaces the redirect behind it.
"""

from __future__ import annotations

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings

# One photo per report in v1 (REPORT_A_PROBLEM.md: "a note and an optional
# photo"). The key is numbered anyway, because the alternative - `photo.jpg` -
# would have to be renamed the day a second one is allowed, and every stored
# key with it.
FIRST_PHOTO_INDEX = 1

# JPEG only, and it is the client that makes that true: #234 has it downscale
# and strip EXIF before upload, which means re-encoding anyway. Accepting
# whatever a phone produces would put HEIC and 12 MB PNGs in a bucket whose
# whole point is that egress is the cost that grows.
ALLOWED_CONTENT_TYPE = "image/jpeg"

# JPEG's start-of-image marker, plus the first byte of the segment that always
# follows it.
#
# The `Content-Type` header the uploader sends is a claim by the sender about
# the sender's own bytes, and it is not the claim that ends up stored: the
# object is written under a key ending `.jpg` with `ContentType: image/jpeg`
# set by `store_photo` - so a mislabelling is not merely recorded here, it is
# asserted by us, and `presigned_photo_url` later hands that assertion to a
# browser. Three bytes of comparison is what makes it true (#379).
JPEG_MAGIC = b"\xff\xd8\xff"

# Comfortably above a downscaled photo and far below an untouched one, so a
# client that skips the resize is refused rather than quietly billed for.
#
# Enforced against the bytes as they ARRIVE, not against the finished buffer -
# see `read_capped_body` in app/routers/reports.py. A limit measured after
# `await request.body()` has already allocated the whole upload has paid the
# exact cost it exists to avoid (#379).
MAX_PHOTO_BYTES = 2 * 1024 * 1024

# How long a signed photo URL stays good for.
#
# Five minutes, and both bounds are real. A signed URL is a bearer token (see
# the header), so the shorter the better - but it is handed to a phone that may
# be on one bar of EDGE, and a URL that expires mid-download turns into a
# broken image that a refresh fixes, which reads as the app being flaky.
# Minutes is enough for the fetch plus a retry, and short enough that a URL
# that leaks - out of a screenshot, a log line, a shared devtools trace - is a
# capability that has already expired by the time anyone acts on it.
#
# **Deliberately not raised for the moderation queue** (#385 asked, and this
# is the answer). A moderator works through twenty reports over an hour, so a
# link minted when the screen loaded is long dead by the time they reach the
# last row. The fix for that is the client asking again - one request, against
# a check that has to run on every view anyway for its answer to mean anything
# - and not a bearer token for a photo of a person that stays good for the
# length of a shift. A TTL nudged upward "because the queue is slow" would be
# the trade above being reversed by a number, without the sentence that
# reverses it ever being written down.
PHOTO_URL_TTL_SECONDS = 300


class PhotoStorageUnavailable(RuntimeError):
    """R2 is not configured, or refused the write.

    One exception for both, deliberately: from the caller's side they are the
    same event - the photo did not land - and the report itself is unaffected
    either way, because the row is the authoritative half.
    """


def photo_key(report_id: str, index: int = FIRST_PHOTO_INDEX) -> str:
    """The object key for a report's photo. Pure, and the only spelling of it.

    Every other module derives keys through this function rather than
    formatting the string itself: a second spelling is how the uploader and
    the sweeper come to disagree about which objects belong to a report.
    """
    return f"reports/{report_id}/{index}.jpg"


def poi_photo_key(poi_id: str, contributor_id: str) -> str:
    """The object key for a community waypoint photo (#576). Pure, and the
    only spelling of it, same rule as `photo_key` above.

    Per POI *and per contributor*, which is what makes the design's own
    rules structural rather than enforced: a hiker's second photo of a
    place overwrites their first (self-replacement is free), and
    one-per-person-per-POI is a property of the key. The caller validates
    `poi_id` before it reaches here - it is client-supplied text going into
    an object key, see the router's guard.
    """
    return f"poi-photos/{poi_id}/{contributor_id}.jpg"


def note_photo_key(note_id: str) -> str:
    """Where a field note's photo lives (#879).

    Keyed by the NOTE rather than by contributor-and-place, which is the one
    structural difference from `poi_photo_key` above and the reason a note
    photo is not simply a community photo. That store holds one photo per
    hiker per waypoint: a hiker who leaves a second note at the same spring
    would replace their first note's photo, so a note reading "dry" would end
    up illustrated by last week's photo of it flowing. A note's picture has
    to be what that hiker saw on that day or it is worse than no picture.
    """
    return f"notes/{note_id}.jpg"


def photo_storage_configured() -> bool:
    """Whether there is a bucket to talk to at all.

    A deployment with no R2 credentials is a normal state (every developer
    machine, every CI run), not a misconfiguration to raise about - it simply
    has no photos, and the endpoints say so rather than failing.
    """
    return bool(
        settings.r2_photo_endpoint_url
        and settings.r2_photo_bucket
        and settings.r2_photo_access_key_id
        and settings.r2_photo_secret_access_key
    )


def photo_uploads_enabled() -> bool:
    """Whether this deployment may WRITE photos.

    Configured, plus the same explicit gate `pipeline/publish.py` uses, for the
    same reason: a process that should not upload should be unable to, rather
    than merely unlikely to.

    Reading is deliberately not gated on the same flag - see
    `photo_storage_configured`. Turning uploads off is a decision about what
    this deployment may add to the bucket, not about whether a moderator may
    look at a photo that is already in it.
    """
    return bool(settings.r2_photo_write_enabled) and photo_storage_configured()


def _client():
    """A fresh S3 client for R2.

    Not cached: this is called once per upload, an upload is already a network
    round trip, and a module-level client would capture credentials at import
    time - which makes the settings above untestable and a rotated key
    unnoticed until a restart.
    """
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_photo_endpoint_url,
        aws_access_key_id=settings.r2_photo_access_key_id,
        aws_secret_access_key=settings.r2_photo_secret_access_key,
        # R2 ignores the region but boto3 insists on one; `auto` is what
        # Cloudflare's own documentation uses.
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def store_photo(report_id: str, body: bytes) -> str:
    """Write a report's photo and return the key that was written.

    Returns the KEY, never a URL: a full URL bakes today's bucket domain into
    every row permanently, and the domain is the part most likely to change
    (the R2.dev subdomain is a documented stopgap - see LAUNCH_CHECKLIST.md).

    Overwrites by design. The key is derived, so a retry of an upload that
    already succeeded rewrites the same object rather than leaving a second
    one nobody can find.
    """
    return store_photo_object(photo_key(report_id), body)


def store_photo_object(key: str, body: bytes) -> str:
    """Write one photo object under a derived key. Everything `store_photo`
    says holds here; the key's derivation is the caller's (`photo_key`,
    `poi_photo_key`), the write's mechanics are one code path."""
    if not photo_uploads_enabled():
        raise PhotoStorageUnavailable("R2 is not configured for photo uploads.")

    try:
        _client().put_object(
            Bucket=settings.r2_photo_bucket,
            Key=key,
            Body=body,
            ContentType=ALLOWED_CONTENT_TYPE,
        )
    except (BotoCoreError, ClientError) as error:  # pragma: no cover - re-raised as one
        raise PhotoStorageUnavailable(str(error)) from error

    return key


def delete_photo_object(key: str) -> None:
    """Remove one photo object.

    This is the half of #576's withdrawal that touches the bucket. Gated on
    the same write flag as uploads - deleting is a write - and the caller
    deletes the ROW first: the row is the authoritative half, so a delete
    that fails here leaves an orphaned object for the reconciliation sweep,
    never a row pointing at nothing.
    """
    if not photo_uploads_enabled():
        raise PhotoStorageUnavailable("R2 is not configured for photo uploads.")

    try:
        _client().delete_object(Bucket=settings.r2_photo_bucket, Key=key)
    except (BotoCoreError, ClientError) as error:  # pragma: no cover - re-raised as one
        raise PhotoStorageUnavailable(str(error)) from error


def presigned_photo_url(report_id: str, expires_in: int = PHOTO_URL_TTL_SECONDS) -> str:
    """A short-lived URL that fetches a report's photo straight from R2.

    **Derived from the report id, never from a stored string**, and that is a
    guard rather than a convention. `photo_url` is settable on `POST /reports`,
    so a client can put any text it likes in it; a serving path that dereferenced
    that value would let a report point at any object in the bucket - another
    report's photo among them - and the visibility check in front of it would be
    checking the wrong report. Building the key here means the only object this
    can ever hand out is the one belonging to the report that was authorised.

    No round trip: presigning is a local signature, so this costs nothing and
    cannot fail for a network reason. It also does not prove the object exists -
    a report whose upload never landed signs a URL that R2 answers with a 404,
    which is the same "no photo" the caller would show anyway, one HEAD request
    cheaper on a connection that is the scarce thing here.
    """
    return presigned_object_url(photo_key(report_id), expires_in=expires_in)


def presigned_object_url(key: str, expires_in: int = PHOTO_URL_TTL_SECONDS) -> str:
    """A short-lived URL for one photo object, by its derived key.

    The signing mechanics and their reasoning live on `presigned_photo_url`
    above; community photos (#576) sign through here with `poi_photo_key`,
    and the derived-key guard holds for them the same way - the only object
    a caller can hand out is the one whose row was just authorised.
    """
    if not photo_storage_configured():
        raise PhotoStorageUnavailable("R2 is not configured for photos.")

    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.r2_photo_bucket, "Key": key},
            ExpiresIn=expires_in,
        )
    except (BotoCoreError, ClientError) as error:  # pragma: no cover - re-raised as one
        raise PhotoStorageUnavailable(str(error)) from error
