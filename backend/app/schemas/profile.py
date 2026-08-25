"""Pydantic response models for the `/profiles` router."""

from pydantic import BaseModel, ConfigDict

from app.core.time import UtcDatetime
from app.models.profile import Role


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: Role
    display_name: str | None
    created_at: UtcDatetime


class DeletionReceipt(BaseModel):
    """What `DELETE /profiles/me` actually did, counted.

    Two halves and they are not the same claim. The `*_deleted` counts are
    rows that no longer exist. `kept` is the half a hiker is more likely to
    be surprised by: the contributions that outlive the account, keyed by
    the words the deletion screen used for them so the receipt and the
    warning cannot drift into describing different things.

    `kept` omits its zeroes rather than listing them - "closures you
    reported: 0" is noise on the receipt of somebody who never reported one,
    and an empty object is the readable way to say "nothing of yours stayed".
    """

    trips_deleted: int
    day_hikes_deleted: int
    planned_hikes_deleted: int
    hikes_deleted: int
    preferences_deleted: int
    assignments_released: int
    hours_deleted: int
    app_failure_reports_unlinked: int
    kept: dict[str, int]
