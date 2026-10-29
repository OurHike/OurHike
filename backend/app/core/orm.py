"""Small helpers for common ORM and HTTP patterns."""

from typing import Any, TypeVar

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

T = TypeVar("T")


def get_or_404(db: Session, model: type[T], object_id: Any, *, detail: str) -> T:
    obj = db.get(model, object_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return obj


def commit_and_refresh(db: Session, obj: T) -> T:
    db.commit()
    db.refresh(obj)
    return obj


def release_before_waiting(db: Session) -> None:
    """End the session's transaction, so its connection goes back to the pool.

    For a route about to await something slow that is not the database: a
    photo's bytes arriving from a phone on one bar, and then R2 storing them
    (#1915 - A photo upload holds a pooled database connection inside an open
    transaction while the phone sends the bytes, so fifteen slow uploads make
    every other read 500). The session stays usable. Its next query checks a
    connection out again and begins a new transaction.

    The commit expires every row the session loaded, so a route must look its
    row up again after the wait instead of trusting the copy it had. It would
    have to anyway: the row can change while the bytes arrive.

    Nor may it read that copy before the wait is over, `current_user.id`
    included. Reading an expired row's attribute reloads the row, and the
    reload is a query: it takes a connection back out of the pool and holds
    it in a new transaction, which undoes this call without saying so.
    Measured 2026-10-29 against a local Postgres: reading `profile.id` after
    a commit emitted `SELECT ... FROM profiles` and left `pool.checkedout()`
    at 1. So whatever the route needs later is taken as a plain value first
    (the upload routes' check steps return the caller's id).

    A commit and not a rollback, because nothing done by then is meant to be
    thrown away (`get_current_user` commits its own writes, and nothing else
    writes before the wait).
    """
    db.commit()
