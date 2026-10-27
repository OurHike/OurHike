"""Where claim photos are kept: a private R2 bucket, read through short-lived signed URLs.

backend/app/core/photos.py's design, for its reasons: the object key is derived
from ids and never stored (the row is authoritative, the object disposable), the
bucket is private, writes sit behind an explicit flag, and a storage failure
reaches the caller as a short sentence while the bucket's address stays in the log.

NOTHING SWEEPS THE BUCKET YET. An object whose row never committed, or whose
delete failed, stays until someone writes the sweep: a set difference between
`claim/{id}/{photo id}` keys and the photo table, which the derived key makes
possible. Photos of released claims are kept, by nobody's decision; both are on
#1910's open list.

Its own bucket and its own STEWARD_R2_* names, never OurHike's R2_* or
R2_PHOTO_*: a deployment that carries OurHike's environment must not be able to
write steward photos into OurHike's buckets.
"""

from __future__ import annotations

import logging
import uuid
from functools import cached_property
from io import BytesIO
from typing import Protocol

from steward_api import limits

logger = logging.getLogger(__name__)

#: How long a signed read URL lasts: long enough to look through a submission.
READ_URL_SECONDS = 600

UNAVAILABLE = "Photo storage is not available right now. Try again shortly."
NOT_SET_UP = "Photo storage is not set up on this deployment."


class PhotoStorageUnavailable(RuntimeError):
    pass


def photo_key(claim_id: uuid.UUID, photo_id: uuid.UUID) -> str:
    """The only spelling of a photo's object key."""
    return f"claims/{claim_id}/{photo_id}"


class PhotoStore(Protocol):
    def put(self, key: str, body: bytes, content_type: str) -> None: ...
    def url(self, key: str) -> str: ...
    def delete(self, key: str) -> None: ...


class MemoryPhotoStore:
    """For tests and local runs: the objects in a dict, and fake URLs."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, body: bytes, content_type: str) -> None:
        self.objects[key] = (body, content_type)

    def url(self, key: str) -> str:
        return f"memory://{key}"

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


class R2PhotoStore:
    def __init__(self, endpoint_url: str, bucket: str, access_key_id: str, secret_access_key: str) -> None:
        self.endpoint_url = endpoint_url
        self.bucket = bucket
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key

    @cached_property
    def _client(self):
        """One client for the store's life: building one costs about 13 ms, and
        every claim read signs a URL per photo (the review's finding 7). boto3
        clients are safe to share between threads."""
        import boto3
        from botocore.config import Config

        return boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self._access_key_id,
            aws_secret_access_key=self._secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=20, retries={"max_attempts": 2}),
        )

    def put(self, key: str, body: bytes, content_type: str) -> None:
        try:
            self._client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)
        except Exception as exc:  # noqa: BLE001 - botocore raises many kinds; all mean the same here
            logger.warning("R2 put failed for %s: %s", key, exc)
            raise PhotoStorageUnavailable(UNAVAILABLE) from exc

    def url(self, key: str) -> str:
        try:
            return self._client.generate_presigned_url(
                "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=READ_URL_SECONDS
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("R2 signing failed for %s: %s", key, exc)
            raise PhotoStorageUnavailable(UNAVAILABLE) from exc

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # noqa: BLE001
            # The row goes regardless, so the object is never served again; it
            # stays in the bucket until a sweep exists (the module docstring).
            logger.warning("R2 delete failed for %s: %s", key, exc)


# --- What an upload becomes ---------------------------------------------------------


class UnusablePhoto(ValueError):
    pass


def reencode(body: bytes) -> bytes:
    """The photo decoded and drawn again as a plain JPEG: at most
    limits.PHOTO_LONG_SIDE on its long side, upright, and carrying no metadata at
    all, because only pixels are copied into a fresh image.

    The web app does the same on the phone, but a check of what arrived is not
    a substitute for this. The adversarial review (2026-10-27, finding 6) got
    past a byte search for EXIF four ways: EXIF after 64 KB of padding, XMP
    GPS tags, a PNG eXIf chunk, and an HTML document behind a JPEG's first
    three bytes. Decoding and redrawing answers all four, and any future fifth,
    because nothing from the upload survives but its pixels.

    Raises UnusablePhoto for anything Pillow cannot read as a JPEG, PNG or WebP,
    or that would decode past limits.PHOTO_MAX_PIXELS.
    """
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        with Image.open(BytesIO(body)) as image:
            if image.format not in ("JPEG", "PNG", "WEBP"):
                raise UnusablePhoto("Only JPEG, PNG and WebP photos are accepted")
            # Checked from the header, before a pixel is decoded: the size a
            # decompression bomb claims is the size it would take.
            if image.width * image.height > limits.PHOTO_MAX_PIXELS:
                raise UnusablePhoto("That photo has more pixels than a phone camera takes")
            upright = ImageOps.exif_transpose(image).convert("RGB")
            upright.thumbnail((limits.PHOTO_LONG_SIDE, limits.PHOTO_LONG_SIDE))
            clean = Image.new("RGB", upright.size)
            clean.paste(upright)
            out = BytesIO()
            clean.save(out, "JPEG", quality=85, optimize=True)
            return out.getvalue()
    except UnusablePhoto:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise UnusablePhoto("That file is not a photo this app can read") from exc
