"""Who may do what in a club's structure survey (#1984).

features/STRUCTURE_INVENTORY.md's permissions table, on top of
`app/core/org_access.py`. Two people are new to that module:

**The survey's volunteer** is anybody with an `inventory_enrollments` row at
the club whose field guide is finished. They need not hold a maintainer
assignment - a roving volunteer is not a maintainer of anything - which is
why `resolve_access` does not know them. The waiver is signed by
construction: the enrolment row is written when it is signed
(app/models/inventory.py).

**The reviewer** is the club's Local Chair, which is any approved club admin
(`is_admin`) - decided by the maintainer by poll on 2026-11-04, over the
alternative of the holders of a role the club picks - or a section
supervisor, narrowed to the sections under their role. The narrowing is the
one new piece of permission logic here, and it is computed the way
`resolve_access` computes `is_supervisor`, so the two cannot disagree about
who supervises.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.org_access import OrgAccess, org_access
from app.db.session import get_db
from app.models.inventory import InventoryEnrollment
from app.models.maintainer_assignment import MaintainerAssignment
from app.models.org_role import OrgRole


def enrollment_of(db: Session, club_id: str, person_id: str) -> InventoryEnrollment | None:
    return (
        db.query(InventoryEnrollment)
        .filter(InventoryEnrollment.club_id == club_id, InventoryEnrollment.person_id == person_id)
        .one_or_none()
    )


def supervised_section_ids(db: Session, club_id: str, person_id: str) -> frozenset[str]:
    """The sections a supervisor reviews: their own, and those under their role.

    "Under their role" means a live assignment, at this club, on a role that
    reports to a role this person holds. Holding a role counts only once the
    assignment is confirmed or was never a proposal - `resolve_access`'s rule
    (#1635), copied rather than re-derived so a proposed lead cannot review
    either. A section a supervisor holds themselves is under their role too.
    An assignment with no section reaches no section, and a retired role
    supervises nobody.
    """
    live = (
        db.query(MaintainerAssignment)
        .filter(
            MaintainerAssignment.club_id == club_id,
            MaintainerAssignment.maintainer_id == person_id,
            MaintainerAssignment.effective_to.is_(None),
        )
        .all()
    )
    held = [a for a in live if a.role_id is not None and (a.proposed_by is None or a.confirmed_at is not None)]
    held_role_ids = {a.role_id for a in held}
    if not held_role_ids:
        return frozenset()

    under_role_ids = {
        role_id
        for (role_id,) in db.query(OrgRole.id).filter(
            OrgRole.club_id == club_id,
            OrgRole.reports_to_role_id.in_(held_role_ids),
            OrgRole.retired_at.is_(None),
        )
    }
    sections = {a.section_id for a in held if a.section_id is not None}
    if under_role_ids:
        sections |= {
            section_id
            for (section_id,) in db.query(MaintainerAssignment.section_id).filter(
                MaintainerAssignment.club_id == club_id,
                MaintainerAssignment.role_id.in_(under_role_ids),
                MaintainerAssignment.effective_to.is_(None),
                MaintainerAssignment.section_id.is_not(None),
            )
        }
    return frozenset(sections)


@dataclass(frozen=True)
class InventoryReviewer:
    access: OrgAccess
    #: None for the Local Chair, who reviews every section. A set for a
    #: section supervisor, who reviews only these - possibly none, which is
    #: an answer rather than an error: a supervisor whose crews hold no
    #: section yet has an empty queue.
    section_ids: frozenset[str] | None

    def may_review(self, section_id: str | None) -> bool:
        """An observation with no section is the Local Chair's alone.

        Nothing places it under anybody's role, so no supervisor can claim
        it; the Chair sees everything.
        """
        if self.section_ids is None:
            return True
        return section_id is not None and section_id in self.section_ids


def require_inventory_volunteer(
    access: OrgAccess = Depends(org_access),
    db: Session = Depends(get_db),
) -> InventoryEnrollment:
    """Enrolled at this club, waiver signed, field guide finished."""
    enrollment = enrollment_of(db, access.club.id, access.person_id)
    if enrollment is None or enrollment.training_completed_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Join this organization's structure survey and finish the field guide first",
        )
    return enrollment


def require_inventory_reviewer(
    access: OrgAccess = Depends(org_access),
    db: Session = Depends(get_db),
) -> InventoryReviewer:
    """The Local Chair, or a section supervisor narrowed to their sections."""
    if access.is_admin:
        return InventoryReviewer(access=access, section_ids=None)
    if access.is_supervisor:
        return InventoryReviewer(access=access, section_ids=supervised_section_ids(db, access.club.id, access.person_id))
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only this organization's admins and section supervisors review survey records",
    )
