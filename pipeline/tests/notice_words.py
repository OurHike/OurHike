"""seeds/notice_words.csv as int_closures__club_notices' rule 2 matches it, for checks that need no warehouse.

A mirror of the model's word matching only (its `field_text` and `hits` CTEs), never of the readings' order: the
dbt unit tests hold the SQL itself, and test_dbt_closures_club_notices.py holds their mocks to the seed files. A
value is compared whole (`exact`, `code`) without case or surrounding space, or by whole words (`words`): every run
of characters that are not letters or digits read as one space, and 'non' joined to the word after it.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

SEEDS = Path(__file__).resolve().parent.parent / "dbt" / "seeds"
FIELDS = ("status", "category", "title", "narrative")


def seed(name: str) -> list[dict]:
    with (SEEDS / f"{name}.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def words_of(value: str) -> str:
    """A value's words as the model's `padded_value` holds them: lowercase, one space between, one each side."""
    text = re.sub(r"\bnon[^a-z0-9]+", "non", value.lower())
    return " " + re.sub(r"[^a-z0-9]+", " ", text).strip() + " "


def readings(field: str, value: str, *, states_only_codes: bool = True) -> set[tuple[str, str]]:
    """Every (reads_as, word) of the vocabulary that `value` holds in `field`. `states_only_codes` is whether every
    status the value's source states is a `code` word, which a `code` row needs (the model's `source_statuses`)."""
    found = set()
    whole = value.strip().lower()
    padded = words_of(value)
    for row in seed("notice_words"):
        if field not in row["read_in"].split():
            continue
        word = row["word"]
        if row["matches"] == "exact":
            hit = whole == word
        elif row["matches"] == "code":
            hit = whole == word and states_only_codes
        else:
            hit = f" {word} " in padded
        if hit:
            found.add((row["reads_as"], word))
    return found


def reads_as(field: str, value: str, **kwargs) -> set[str]:
    return {reading for reading, _ in readings(field, value, **kwargs)}
