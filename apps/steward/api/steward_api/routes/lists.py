"""Saved lists of sites, and their share links (PLAN.md §8 `list`, `list_item`).

A list belongs to one person. Anybody else asking for it by id gets 404, not
403, so ids cannot be probed for existence. Sharing is by a random token the
owner hands out; opening one needs sign-in (§8) and shows the list read-only.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from steward_api import limits
from steward_api.auth import current_user
from steward_api.db import get_db
from steward_api.models import SiteList, SiteListItem, StewardUser
from steward_api.schemas import ListCreate, ListDetail, ListRename, ListSummary, SharedList, SharedLookup, ShareLink

router = APIRouter(tags=["lists"])

RimsIdPath = Path(pattern=limits.RIMS_ID_PATTERN)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _summary(site_list: SiteList) -> ListSummary:
    return ListSummary(
        id=site_list.id,
        name=site_list.name,
        item_count=len(site_list.items),
        shared=site_list.share_token_sha256 is not None,
        created_at=site_list.created_at,
        updated_at=site_list.updated_at,
    )


def _detail(site_list: SiteList) -> ListDetail:
    return ListDetail(**_summary(site_list).model_dump(), rims_ids=[item.rims_id for item in site_list.items])


def _own_list(db: Session, user: StewardUser, list_id: uuid.UUID) -> SiteList:
    site_list = db.get(SiteList, list_id)
    if site_list is None or site_list.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such list")
    return site_list


@router.get("/lists", response_model=list[ListSummary])
def my_lists(user: StewardUser = Depends(current_user), db: Session = Depends(get_db)) -> list[ListSummary]:
    lists = db.scalars(select(SiteList).where(SiteList.owner_id == user.id).order_by(SiteList.updated_at.desc())).all()
    return [_summary(site_list) for site_list in lists]


@router.post("/lists", response_model=ListDetail, status_code=status.HTTP_201_CREATED)
def create_list(body: ListCreate, user: StewardUser = Depends(current_user), db: Session = Depends(get_db)) -> ListDetail:
    owned = db.scalar(select(func.count()).select_from(SiteList).where(SiteList.owner_id == user.id)) or 0
    if owned >= limits.LISTS_PER_USER:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"You already have {limits.LISTS_PER_USER} lists, the most one account can keep"
        )
    site_list = SiteList(owner_id=user.id, name=body.name)
    site_list.items = [SiteListItem(rims_id=rims_id) for rims_id in dict.fromkeys(body.rims_ids)]
    db.add(site_list)
    db.commit()
    db.refresh(site_list)
    return _detail(site_list)


@router.get("/lists/{list_id}", response_model=ListDetail)
def read_list(list_id: uuid.UUID, user: StewardUser = Depends(current_user), db: Session = Depends(get_db)) -> ListDetail:
    return _detail(_own_list(db, user, list_id))


@router.patch("/lists/{list_id}", response_model=ListDetail)
def rename_list(
    list_id: uuid.UUID, body: ListRename, user: StewardUser = Depends(current_user), db: Session = Depends(get_db)
) -> ListDetail:
    site_list = _own_list(db, user, list_id)
    site_list.name = body.name
    db.commit()
    db.refresh(site_list)
    return _detail(site_list)


@router.delete("/lists/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_list(list_id: uuid.UUID, user: StewardUser = Depends(current_user), db: Session = Depends(get_db)) -> None:
    db.delete(_own_list(db, user, list_id))
    db.commit()


@router.put("/lists/{list_id}/items/{rims_id}", status_code=status.HTTP_204_NO_CONTENT)
def add_item(
    list_id: uuid.UUID,
    rims_id: str = RimsIdPath,
    user: StewardUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    """Idempotent: saving a site twice keeps one entry."""
    site_list = _own_list(db, user, list_id)
    if any(item.rims_id == rims_id for item in site_list.items):
        return
    if len(site_list.items) >= limits.ITEMS_PER_LIST:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A list holds at most {limits.ITEMS_PER_LIST} sites")
    site_list.items.append(SiteListItem(rims_id=rims_id))
    site_list.updated_at = func.now()
    try:
        db.commit()
    except IntegrityError:
        # The same site saved twice at once: the other request's row is this one's.
        db.rollback()


@router.delete("/lists/{list_id}/items/{rims_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(
    list_id: uuid.UUID,
    rims_id: str = RimsIdPath,
    user: StewardUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    site_list = _own_list(db, user, list_id)
    site_list.items = [item for item in site_list.items if item.rims_id != rims_id]
    site_list.updated_at = func.now()
    db.commit()


@router.post("/lists/{list_id}/share", response_model=ShareLink)
def share_list(list_id: uuid.UUID, user: StewardUser = Depends(current_user), db: Session = Depends(get_db)) -> ShareLink:
    """A new share token, replacing any earlier one: sharing again is how a leaked link is revoked."""
    site_list = _own_list(db, user, list_id)
    token = secrets.token_urlsafe(24)
    site_list.share_token_sha256 = token_hash(token)
    db.commit()
    return ShareLink(token=token)


@router.delete("/lists/{list_id}/share", status_code=status.HTTP_204_NO_CONTENT)
def unshare_list(list_id: uuid.UUID, user: StewardUser = Depends(current_user), db: Session = Depends(get_db)) -> None:
    site_list = _own_list(db, user, list_id)
    site_list.share_token_sha256 = None
    db.commit()


@router.post("/shared", response_model=SharedList)
def open_shared(body: SharedLookup, _user: StewardUser = Depends(current_user), db: Session = Depends(get_db)) -> SharedList:
    """The token travels in the body rather than the path, so it stays out of
    access logs. Sign-in is required (PLAN.md §8); any signed-in user may open it."""
    site_list = db.scalar(select(SiteList).where(SiteList.share_token_sha256 == token_hash(body.token)))
    if site_list is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This share link is not valid. Its owner may have replaced or stopped it.")
    owner = db.get(StewardUser, site_list.owner_id)
    return SharedList(
        name=site_list.name,
        owner=owner.display_name if owner else None,
        rims_ids=[item.rims_id for item in site_list.items],
        updated_at=site_list.updated_at,
    )
