"""Request/response models for an organization's three-tier registry.

See ../../../features/ORG_ONBOARDING.md and #1540. The tiers are park or
system, then trail, then section; the top one is allowed to be thin.

**None of these publish anything.** Writing here produces the organization's
proposal in a form the console can show them; the bytes on a hiker's phone
still come out of `pipeline/export_club_sections.py` after a person merges a
pull request. SOURCE_REGISTRY.md's rule survives self-service, and these
models are where it would be easiest to accidentally break it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.time import UtcDatetime
from app.models.org_registry import ParkKind
from app.schemas.common import FiniteFloat, NoteText

# What a GIS source may be. Each of these can be **re-read** - fetched again
# tomorrow and diffed against what we hold - which is the whole criterion.
#
# A PDF, a screenshot or a spreadsheet is refused for that reason and not for
# a technical one: accepting a snapshot while implying a feed is the failure,
# because the nightly re-read then silently never happens and the registry
# quietly ages into fiction. The refusal is stated in the UI rather than
# being a validation error a form swallows.
READABLE_SOURCE_KINDS = ("arcgis", "wfs", "geojson", "shapefile_zip")

FLAT_FILE_SUFFIXES = (".pdf", ".xlsx", ".xls", ".csv", ".doc", ".docx", ".png", ".jpg", ".jpeg")


class OrgSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trail_id: str
    name: str
    start_anchor: str | None
    end_anchor: str | None
    start_mile: float | None
    end_mile: float | None
    miles: float | None
    region: str | None
    geometry: str | None


class OrgSectionCreate(BaseModel):
    name: str
    start_anchor: str | None = None
    end_anchor: str | None = None
    start_mile: FiniteFloat | None = None
    end_mile: FiniteFloat | None = None
    miles: FiniteFloat | None = None
    region: str | None = None
    geometry: str | None = None

    @field_validator("start_mile", "end_mile", "miles")
    @classmethod
    def _no_negative_distances(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("a distance along the trail cannot be negative")
        return value


class OrgTrailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    park_id: str
    name: str | None
    blaze_value_raw: str | None
    blaze_mapped: str | None
    miles: float | None
    sections: list[OrgSectionOut] = []


class OrgTrailCreate(BaseModel):
    """A trail with no name and no blaze is legitimate - see the model.

    Neither field has a default beyond None, and nothing below requires one.
    A route on a map is a real thing organizations publish, and anything that
    demanded a name here would collect a fake one.
    """

    name: str | None = None
    blaze_value_raw: str | None = None
    blaze_mapped: str | None = None
    miles: FiniteFloat | None = None


class OrgParkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    name: str
    kind: ParkKind
    created_at: UtcDatetime
    trails: list[OrgTrailOut] = []


class OrgParkCreate(BaseModel):
    name: str
    kind: ParkKind = ParkKind.park


class GisSourceCreate(BaseModel):
    """Registering a server we can re-read, and refusing one we cannot."""

    url: str
    kind: str
    label: str | None = None
    note: NoteText | None = None

    @field_validator("kind")
    @classmethod
    def _something_re_readable(cls, value: str) -> str:
        if value not in READABLE_SOURCE_KINDS:
            raise ValueError(f"a source has to be one we can re-read: {', '.join(READABLE_SOURCE_KINDS)}")
        return value

    @field_validator("url")
    @classmethod
    def _not_a_flat_file(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.lower().startswith(("http://", "https://")):
            raise ValueError("give an http or https URL we can fetch")
        # The path only - a query string can legitimately contain ".csv" as
        # a format parameter on an endpoint that is perfectly re-readable.
        path = cleaned.split("?", 1)[0].split("#", 1)[0].lower()
        if path.endswith(FLAT_FILE_SUFFIXES):
            raise ValueError(
                "we cannot take a PDF, a spreadsheet or an image as a source - "
                "we need something we can read again tomorrow and compare"
            )
        return cleaned


class RegistryDiffRow(BaseModel):
    """One line of proposed-versus-live.

    `kind` is `added | changed | removed`, and `removed` is the one that
    matters: a nightly re-read that stops seeing a section is either a real
    retirement or an upstream outage, and the two look identical from here.
    So a removal is a proposal like any other and is never applied
    automatically - which is rule 2, and is why this is a diff rather than a
    sync.
    """

    kind: str
    tier: str
    name: str
    detail: str | None = None


class RegistryDiffOut(BaseModel):
    club_id: str
    rows: list[RegistryDiffRow] = []
    # Whether anything here would change what a hiker sees. False for a diff
    # that only touches names and notes, which is worth telling an org
    # because it decides how carefully they read it.
    touches_published_geometry: bool = False


class CoverageGap(BaseModel):
    """A section with no live role attached.

    **A gap is flagged, not escalated**, and nothing here reaches a hiker.
    Most gaps fill within a season, and treating each as an incident trains
    people to ignore the report.
    """

    section_id: str
    section_name: str
    trail_name: str | None
    region: str | None
    miles: float | None
    geometry: str | None


class CoverageOut(BaseModel):
    club_id: str
    region: str | None
    sections_total: int
    gaps: list[CoverageGap] = []
