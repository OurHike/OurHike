"""`/clubs/{slug}/registry` - an organization's own three-tier trail list.

See ../../../features/ORG_ONBOARDING.md and #1540.

**NOTHING HERE PUBLISHES ANYTHING, and that is structural rather than a
matter of anybody's discipline.** Writing a park, a trail or a section makes
a row in this backend's database. What a hiker downloads comes out of
`pipeline/export_club_sections.py` and reaches them only after a person
merges a pull request. There is no endpoint in this file that touches a
published artifact, and there must never be one - SOURCE_REGISTRY.md's rule
that nothing self-service changes a hiker's map without a merge is what makes
it safe to give an outside organization a seat at all.

So `POST /clubs/{slug}/registry/signoff` records that three codeowners agree.
It does not ship anything. The thing it produces is a proposal a maintainer
merges, and the screen says so in as many words.
"""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.org_access import OrgAccess, club_by_slug, org_access, require_org_admin
from app.core.orm import commit_and_refresh
from app.core.registry_pr import RegistryPrRefused, open_registry_pr
from app.db.session import get_db
from app.models.club import OrgAdmin
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.org_registry import OrgPark, OrgSection, OrgTrail, RegistrySignoff
from app.schemas.org_registry import (
    CoverageGap,
    CoverageOut,
    GisSourceCreate,
    OrgParkCreate,
    OrgParkOut,
    OrgSectionCreate,
    OrgSectionOut,
    OrgTrailCreate,
    OrgTrailOut,
    RegistryDiffOut,
    RegistryDiffRow,
)

router = APIRouter(prefix="/clubs", tags=["org-registry"])

# How many codeowners have to agree before a registry change is a proposal
# anybody will merge. Three, against one everywhere else - see
# ORG_ONBOARDING.md: three-for-everything makes small corrections cost more
# than they are worth, and the corrections then stop happening.
REGISTRY_APPROVALS_REQUIRED = 3


def _park_or_404(db: Session, club_id: str, park_id: str) -> OrgPark:
    park = db.query(OrgPark).filter(OrgPark.id == park_id, OrgPark.club_id == club_id).one_or_none()
    if park is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such park or system here")
    return park


def _trail_or_404(db: Session, club_id: str, trail_id: str) -> OrgTrail:
    trail = (
        db.query(OrgTrail)
        .join(OrgPark, OrgPark.id == OrgTrail.park_id)
        .filter(OrgTrail.id == trail_id, OrgPark.club_id == club_id)
        .one_or_none()
    )
    if trail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such trail here")
    return trail


def _read_registry(db: Session, club_id: str) -> list[OrgParkOut]:
    """The whole registry, assembled in three queries rather than N+1.

    The sign-off screen renders every tier at once - 312 sections in the
    design's own example - so a lazy relationship per trail would be several
    hundred round trips to draw one table.
    """
    parks = db.query(OrgPark).filter(OrgPark.club_id == club_id).order_by(OrgPark.name).all()
    park_ids = [park.id for park in parks]
    trails = db.query(OrgTrail).filter(OrgTrail.park_id.in_(park_ids)).order_by(OrgTrail.name).all() if park_ids else []
    trail_ids = [trail.id for trail in trails]
    sections = (
        db.query(OrgSection).filter(OrgSection.trail_id.in_(trail_ids)).order_by(OrgSection.start_mile).all() if trail_ids else []
    )

    sections_by_trail: dict[str, list[OrgSectionOut]] = {}
    for section in sections:
        sections_by_trail.setdefault(section.trail_id, []).append(OrgSectionOut.model_validate(section))

    trails_by_park: dict[str, list[OrgTrailOut]] = {}
    for trail in trails:
        out = OrgTrailOut.model_validate(trail)
        out.sections = sections_by_trail.get(trail.id, [])
        trails_by_park.setdefault(trail.park_id, []).append(out)

    result = []
    for park in parks:
        park_out = OrgParkOut.model_validate(park)
        park_out.trails = trails_by_park.get(park.id, [])
        result.append(park_out)
    return result


@router.get("/{slug}/registry", response_model=list[OrgParkOut])
def read_registry(slug: str, db: Session = Depends(get_db)) -> list[OrgParkOut]:
    """An organization's registry, whole.

    Public, because this is what the organization publishes about its own
    trails and the demo org at `/for-orgs/demo` is exactly this endpoint with
    a different slug. The roster and the hours are the private half and live
    elsewhere.
    """
    return _read_registry(db, club_by_slug(db, slug).id)


@router.post("/{slug}/registry/parks", response_model=OrgParkOut, status_code=status.HTTP_201_CREATED)
def add_park(
    slug: str,
    payload: OrgParkCreate,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> OrgParkOut:
    """Add a park, system or forest. The top tier may be thin without being wrong."""
    park = OrgPark(club_id=access.club.id, name=payload.name, kind=payload.kind)
    db.add(park)
    return OrgParkOut.model_validate(commit_and_refresh(db, park))


@router.post("/{slug}/registry/parks/{park_id}/trails", response_model=OrgTrailOut, status_code=status.HTTP_201_CREATED)
def add_trail(
    slug: str,
    park_id: str,
    payload: OrgTrailCreate,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> OrgTrailOut:
    """Add a trail. A nameless, blazeless one is legitimate - see the model."""
    _park_or_404(db, access.club.id, park_id)
    trail = OrgTrail(
        park_id=park_id,
        name=payload.name,
        blaze_value_raw=payload.blaze_value_raw,
        blaze_mapped=payload.blaze_mapped,
        miles=payload.miles,
    )
    db.add(trail)
    return OrgTrailOut.model_validate(commit_and_refresh(db, trail))


@router.post(
    "/{slug}/registry/trails/{trail_id}/sections",
    response_model=OrgSectionOut,
    status_code=status.HTTP_201_CREATED,
)
def add_section(
    slug: str,
    trail_id: str,
    payload: OrgSectionCreate,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> OrgSectionOut:
    """Add a section - the stretch one volunteer looks after."""
    _trail_or_404(db, access.club.id, trail_id)
    section = OrgSection(
        trail_id=trail_id,
        name=payload.name,
        start_anchor=payload.start_anchor,
        end_anchor=payload.end_anchor,
        start_mile=payload.start_mile,
        end_mile=payload.end_mile,
        miles=payload.miles,
        region=payload.region,
        geometry=payload.geometry,
    )
    db.add(section)
    return OrgSectionOut.model_validate(commit_and_refresh(db, section))


@router.post("/{slug}/gis-source", status_code=status.HTTP_202_ACCEPTED)
def register_gis_source(
    slug: str,
    payload: GisSourceCreate,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Register a server we can re-read, and refuse anything we cannot.

    **We check, we do not take their word.** The probe itself - fetch it
    once, read-only, and report the feature count, the geometry type, the
    declared CRS, the transfer size - belongs to the pipeline and is
    SOURCE_REGISTRY.md's `1o`. This endpoint records the registration and
    says plainly that a person will run that probe, rather than returning a
    pretended result.

    The flat-file refusal happens in the schema, where it names its own
    reason: a PDF or a spreadsheet cannot be read again tomorrow, so
    accepting one would be accepting a snapshot while implying a feed.
    """
    return {
        "status": "registered",
        "detail": (
            f"We will read {payload.url} and come back with what we found - the feature count, "
            "the geometry type, the projection it declares and how big it is. "
            "Nothing from it reaches a hiker until your codeowners approve the result."
        ),
        "org": access.club.slug or access.club.id,
    }


@router.get("/{slug}/registry/diff", response_model=RegistryDiffOut)
def read_registry_diff(
    slug: str,
    access: OrgAccess = Depends(org_access),
    db: Session = Depends(get_db),
) -> RegistryDiffOut:
    """Proposed against live - what sign-off is agreeing to.

    Backs the sign-off screen and the nightly re-read alike, because they are
    the same question asked by two callers. **Our own automation proposes; it
    does not publish** - a re-read that stops seeing a section is either a
    real retirement or an upstream outage, and from here the two are
    identical, so a removal is a proposal like any other.

    Today this reports the registry as entirely proposed while nothing has
    been published for this org - which is the true answer for an org that
    has never signed off, and the shape the diff takes once the pipeline
    side lands.
    """
    if not access.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an approved admin can read an unpublished registry",
        )

    parks = _read_registry(db, access.club.id)
    rows: list[RegistryDiffRow] = []
    for park in parks:
        rows.append(RegistryDiffRow(kind="added", tier="park", name=park.name, detail=park.kind.value))
        for trail in park.trails:
            rows.append(
                RegistryDiffRow(
                    kind="added",
                    tier="trail",
                    name=trail.name or "(unnamed route)",
                    detail=trail.blaze_value_raw,
                )
            )
            for section in trail.sections:
                rows.append(
                    RegistryDiffRow(
                        kind="added",
                        tier="section",
                        name=section.name,
                        detail=f"{section.start_anchor or '?'} → {section.end_anchor or '?'}",
                    )
                )
    return RegistryDiffOut(
        club_id=access.club.id,
        rows=rows,
        touches_published_geometry=any(row.tier == "section" for row in rows),
    )


def registry_fingerprint(db: Session, club_id: str) -> str:
    """A digest of exactly what a codeowner is being asked to sign.

    **WHAT IS IN IT IS THE WHOLE QUESTION.** Every park, trail and section
    this organization publishes, with the fields a hiker would notice being
    wrong: the names, the blazes, the anchors and the mileages. A change to
    any of them produces a different digest, which drops the sign-off count
    back to zero and asks the three again.

    What is deliberately NOT in it: ids and timestamps. A row rewritten with
    the same content is the same registry, and making a re-import invalidate
    three signatures would train an organization to click through the one
    screen that is supposed to make them read.

    Sorted before hashing, because a database is free to return rows in any
    order and a digest that moved with the query plan would be a digest that
    invalidated itself at random.
    """
    parks = db.query(OrgPark).filter(OrgPark.club_id == club_id).all()
    park_ids = [park.id for park in parks]
    trails = db.query(OrgTrail).filter(OrgTrail.park_id.in_(park_ids)).all() if park_ids else []
    trail_ids = [trail.id for trail in trails]
    sections = db.query(OrgSection).filter(OrgSection.trail_id.in_(trail_ids)).all() if trail_ids else []

    lines = sorted(f"park\x1f{park.name}\x1f{park.kind}" for park in parks)
    lines += sorted(
        f"trail\x1f{trail.name}\x1f{trail.blaze_value_raw}\x1f{trail.blaze_mapped}\x1f{trail.miles}" for trail in trails
    )
    lines += sorted(
        f"section\x1f{section.name}\x1f{section.start_anchor}\x1f{section.end_anchor}"
        f"\x1f{section.start_mile}\x1f{section.end_mile}\x1f{section.miles}\x1f{section.region}"
        for section in sections
    )
    return hashlib.sha256("\x1e".join(lines).encode("utf-8")).hexdigest()


@router.post("/{slug}/registry/signoff", status_code=status.HTTP_202_ACCEPTED)
def sign_off_registry(
    slug: str,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Record that this codeowner agrees the registry is accurate.

    **IT PUBLISHES NOTHING, AND IT DOES NOT OPEN A PULL REQUEST EITHER.** The
    first sentence was always true; the second is the correction. An earlier
    version of this endpoint answered `"recorded"` while writing nothing at
    all, and promised a pull request that no code in this repository opens -
    two claims a reader would have had no way to check. Both are now what
    they say: the signature is a row, and the response says plainly that
    opening the pull request is a step nobody has built.

    **A SIGNATURE IS AGAINST ONE EXACT REGISTRY.** `registry_fingerprint`
    digests what the signer read, so adding a trail after two people have
    agreed drops the count rather than carrying their names onto sections
    they never saw. This is the guarantee the whole screen exists for.

    **SIGNING TWICE IS NOT TWO SIGNATURES.** The count is over distinct
    people, so a codeowner pressing the button again cannot reach three
    alone. That is the failure this would have had if it counted rows.

    WHOSE CREDENTIALS WOULD OPEN THE PULL REQUEST, when somebody builds it:
    not the admin's. An organization admin has no GitHub account here, and
    giving one the ability to cause a push would make every org admin a
    committer to a public repository. It has to be a service identity with
    write scoped to the registry path and nothing else, and a person still
    merges. That is a decision to make in review rather than a detail to
    settle in this docstring - features/ORG_ONBOARDING.md's "Known gaps"
    carries it as an open question.
    """
    if not access.is_codeowner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signing off the registry is a codeowner's act",
        )

    fingerprint = registry_fingerprint(db, access.club.id)
    already = (
        db.query(RegistrySignoff)
        .filter(
            RegistrySignoff.club_id == access.club.id,
            RegistrySignoff.person_id == access.person_id,
            RegistrySignoff.fingerprint == fingerprint,
        )
        .one_or_none()
    )
    if already is None:
        db.add(
            RegistrySignoff(
                club_id=access.club.id,
                person_id=access.person_id,
                fingerprint=fingerprint,
            )
        )
        db.commit()

    signed_by = {
        row.person_id
        for row in db.query(RegistrySignoff).filter(
            RegistrySignoff.club_id == access.club.id,
            RegistrySignoff.fingerprint == fingerprint,
        )
    }
    codeowners = (
        db.query(OrgAdmin)
        .filter(
            OrgAdmin.club_id == access.club.id,
            OrgAdmin.is_codeowner.is_(True),
            OrgAdmin.approved_at.isnot(None),
        )
        .count()
    )
    complete = len(signed_by) >= REGISTRY_APPROVALS_REQUIRED

    # THE THIRD SIGNATURE RAISES THE PULL REQUEST, which is the connection
    # that used to be missing - agreement produced three rows and stopped,
    # and the console screens described a pull request nothing opened.
    #
    # **AFTER THE SIGNATURE IS COMMITTED, AND NEVER INSIDE ITS TRANSACTION.**
    # The signature is this organization's own record; GitHub being down
    # must not undo three people's agreement. So a refusal here is caught,
    # reported in words, and leaves everything already written alone.
    raised: str | None = None
    if complete:
        try:
            opened = open_registry_pr(db, access.club)
        except RegistryPrRefused:
            # Deliberately not surfaced verbatim: the message can name the
            # repository or the reason a token was refused, and this answer
            # goes to an organization admin.
            pass
        else:
            access.club.registry_pr_number = opened.number
            access.club.registry_pr_url = opened.url
            db.commit()
            raised = opened.url

    return {
        "status": "signed",
        "registry_fingerprint": fingerprint,
        "signatures": len(signed_by),
        "approvals_required": REGISTRY_APPROVALS_REQUIRED,
        "codeowners_available": codeowners,
        "complete": complete,
        "pull_request": raised,
        "detail": (
            (
                (
                    "All three have signed this exact registry, and it is now a pull request "
                    "against the public repository. Your codeowners are asked to approve it there "
                    "with their own GitHub accounts. Approved is still not published - a "
                    "maintainer merges it, and the next map build is what reaches a phone."
                )
                if raised is not None
                else (
                    "All three have signed this exact registry. The pull request could not be "
                    "opened just now, so nothing is waiting for your codeowners yet - your "
                    "signatures are safe and pressing sign off again will try it. Approved is "
                    "not published, and the org home screen tracks the gap."
                )
            )
            if complete
            else (
                f"Signed. {len(signed_by)} of {REGISTRY_APPROVALS_REQUIRED} codeowners have agreed "
                "to this exact registry. Changing a section after somebody signs asks them again - "
                "their name never carries onto sections they did not read. Nothing reaches a phone "
                "until a pull request is merged and the next map build runs: approved is not "
                "published."
            )
        ),
    }


@router.get("/{slug}/coverage", response_model=CoverageOut)
def read_coverage(
    slug: str,
    region: str | None = None,
    access: OrgAccess = Depends(org_access),
    db: Session = Depends(get_db),
) -> CoverageOut:
    """Sections with no live role attached, optionally within one region.

    **A gap is flagged, not escalated, and no hiker is told.** Most gaps fill
    within a season, and treating each as an incident trains people to ignore
    the report - which is why this is gated to people who can act on it
    rather than being a public signal about which miles nobody is looking
    after.

    "No role attached" means no *live* assignment: `effective_to is None` is
    the whole definition of current here, which is what makes coverage
    correct after a hand-off rather than after somebody remembers to tidy up.
    """
    if not access.can_read_roster:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The coverage report is for admins and supervisors here",
        )

    query = (
        db.query(OrgSection, OrgTrail)
        .join(OrgTrail, OrgTrail.id == OrgSection.trail_id)
        .join(OrgPark, OrgPark.id == OrgTrail.park_id)
        .filter(OrgPark.club_id == access.club.id)
    )
    if region:
        query = query.filter(OrgSection.region == region)
    rows = query.order_by(OrgSection.name).all()

    covered = {
        assignment.section_id
        for assignment in db.query(MaintainerAssignment)
        .filter(
            MaintainerAssignment.club_id == access.club.id,
            MaintainerAssignment.effective_to.is_(None),
            MaintainerAssignment.section_id.isnot(None),
        )
        .all()
    }

    gaps = [
        CoverageGap(
            section_id=section.id,
            section_name=section.name,
            trail_name=trail.name,
            region=section.region,
            miles=section.miles,
            geometry=section.geometry,
        )
        for section, trail in rows
        if section.id not in covered
    ]
    return CoverageOut(club_id=access.club.id, region=region, sections_total=len(rows), gaps=gaps)
