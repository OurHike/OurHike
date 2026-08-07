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

So objects are written private, and reading them is a separate, authorising
path (a Worker that checks the owning report's visibility and status before
streaming - not built here, and named so nobody assumes this module made the
photo reachable).
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

# Comfortably above a downscaled photo and far below an untouched one, so a
# client that skips the resize is refused rather than quietly billed for.
MAX_PHOTO_BYTES = 2 * 1024 * 1024


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


def photo_uploads_enabled() -> bool:
    """Whether this deployment may write photos at all.

    The same explicit gate `pipeline/publish.py` uses, for the same reason: a
    process that should not upload should be unable to, rather than merely
    unlikely to. A deployment with no R2 credentials is a normal state (every
    developer machine, every CI run), not a misconfiguration to raise about -
    it simply cannot take photos, and the endpoint says so.
    """
    return bool(
        settings.r2_write_enabled
        and settings.r2_endpoint_url
        and settings.r2_bucket
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
    )


def _client():
    """A fresh S3 client for R2.

    Not cached: this is called once per upload, an upload is already a network
    round trip, and a module-level client would capture credentials at import
    time - which makes the settings above untestable and a rotated key
    unnoticed until a restart.
    """
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
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
    if not photo_uploads_enabled():
        raise PhotoStorageUnavailable("R2 is not configured for photo uploads.")

    key = photo_key(report_id)
    try:
        _client().put_object(
            Bucket=settings.r2_bucket,
            Key=key,
            Body=body,
            ContentType=ALLOWED_CONTENT_TYPE,
        )
    except (BotoCoreError, ClientError) as error:  # pragma: no cover - re-raised as one
        raise PhotoStorageUnavailable(str(error)) from error

    return key
