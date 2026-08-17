"""The one PATCH-null convention, shared by every partial-update schema.

The decision (#255): **an explicit null clears a nullable field; an explicit
null on a non-nullable field is a 422.** Before this, the two PATCH endpoints
answered the question opposite ways - hikes kept explicit nulls through
`exclude_unset` and died on the `nullable=False` column as an unhandled 500,
closures guarded every assignment with `is not None` and silently dropped the
one edit that legitimately clears a field. Neither endpoint had a client
caller yet, which is exactly when a convention is cheap to unify.

`reject_explicit_null` is the non-nullable half. The nullable half lives at
the call sites: routers consult `model_fields_set` (or apply
`model_dump(exclude_unset=True)` wholesale) so that a null which survived
validation is a deliberate clear.
"""

from typing import Any

from pydantic import model_validator


def reject_explicit_null(*field_names: str) -> Any:
    """A `model_validator` that 422s an explicit null on the named fields.

    For update-schema fields backed by `nullable=False` columns: there is no
    null state for the null to mean, so the honest answer is a validation
    error naming the field - not an IntegrityError-shaped 500 and not a
    silent drop. Runs in `mode="before"`, so it sees the raw payload and can
    tell `{"field": null}` from an omitted field, which the validated model's
    field values alone cannot.

    Assign the result in the class body::

        class ThingUpdate(BaseModel):
            name: str | None = None
            _no_explicit_nulls = reject_explicit_null("name")

    The annotation keeps `| None` so the field stays optional; this validator
    is what makes "optional" mean omittable rather than nullable.
    """

    @model_validator(mode="before")
    @classmethod
    def _reject(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for name in field_names:
                if name in data and data[name] is None:
                    raise ValueError(f"{name} cannot be null - omit the field to leave it unchanged")
        return data

    return _reject
