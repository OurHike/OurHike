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
