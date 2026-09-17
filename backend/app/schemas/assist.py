"""What an assist panel may be asked, and what comes back.

**THE PANEL IS AN ENUM AND THE SYSTEM PROMPT IS NOT A FIELD.** A caller who
could supply the system prompt could turn an organization's budget into a
general-purpose model endpoint on somebody else's key, and a caller who could
supply the model could pick the expensive one. Neither is here to be reached:
`app/routers/assist.py` looks the prompt up by panel, and
`app/core/assist.py` reads the model from settings.

**THE QUESTION HAS A CEILING, AND IT IS SMALL.** These panels answer a
sentence about a GIS layer, not a document. A long field is a way to spend a
budget in one call, and the cap is what makes the daily number mean what it
says.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

from app.core.time import UtcDatetime

AssistPanel = Literal["registry", "addtrail", "coverage", "nominate"]

# Long enough for a paragraph about a GIS server and a list of a dozen gap
# names, short enough that no single call can spend a meaningful part of a
# day. @unvalidated: nobody has measured what a real question runs to, and
# `assist_usage` is what will answer it.
QUESTION_MAX = 4_000
WEBSITE_MAX = 500


class AssistAsk(BaseModel):
    panel: AssistPanel
    question: str

    @field_validator("question")
    @classmethod
    def _a_question_rather_than_a_document(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("ask something")
        if len(cleaned) > QUESTION_MAX:
            raise ValueError(f"that is longer than {QUESTION_MAX} characters")
        return cleaned


class NominateAsk(BaseModel):
    """The public panel takes a website and nothing else.

    Free text here would be the internet's own prompt box on our key. A URL
    is the smallest thing the panel needs to do its job, and it is checked
    the same way an organization's own links are - see
    `app/schemas/org.py`'s `safe_external_url` for why an allow-list.
    """

    website: str

    @field_validator("website")
    @classmethod
    def _a_web_address(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > WEBSITE_MAX:
            raise ValueError(f"give a web address under {WEBSITE_MAX} characters")
        if not cleaned.lower().startswith(("https://", "http://")):
            raise ValueError("a web address starts with https:// or http://")
        if any(ord(character) < 0x20 or ord(character) == 0x7F for character in cleaned):
            raise ValueError("that address contains a control character")
        return cleaned


class AssistOut(BaseModel):
    panel: AssistPanel
    answer: str
    tokens_used: int
    # None on the public panel: telling an anonymous caller how much of a
    # shared-by-address budget is left is telling them how much is left to
    # spend, which is a different sentence from the one an organization reads
    # about its own.
    tokens_left_today: int | None = None


class AssistConsentUpdate(BaseModel):
    """An organization saying yes or no to the panels reading its data.

    One boolean, and deliberately nothing else. Not part of
    `OrgSettingsUpdate` for two reasons worth stating: that model is a PATCH
    whose fields are written straight onto the row, which cannot record
    *who* agreed or *when*; and burying consent among the website and
    donation links would make it one more field somebody tabs through rather
    than a decision they took.
    """

    opted_in: bool


class AssistConsentOut(BaseModel):
    """Where an organization's consent stands, and who put it there.

    Behind the admin gate rather than on `OrgOut`, which is public. That an
    organization uses the panels is a fact about the organization; which of
    its admins clicked the button on which afternoon is a fact about a
    person, and it does not need to be on a page a hiker can read.

    Built field by field in the router rather than validated off the row:
    the column names carry an `assist_` prefix the response does not need,
    and a silent name mismatch under `from_attributes` would answer `false`
    for an org that had agreed.
    """

    opted_in: bool
    opted_in_at: UtcDatetime | None = None
    opted_in_by: str | None = None
    opted_out_at: UtcDatetime | None = None
