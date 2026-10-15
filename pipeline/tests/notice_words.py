"""seeds/notice_words.csv as int_closures__club_notices' rule 2 matches it, for checks that need no warehouse.

A mirror of the model's word matching only (its `field_text` and `hits` CTEs), never of the readings' order: the
dbt unit tests hold the SQL itself, and test_dbt_closures_club_notices.py holds their mocks to the seed files. A
value is compared whole (`exact`, `code`) without case or surrounding space, or by whole words (`words`): every run
of characters that are not letters or digits read as one space, and 'non' joined to the word after it. A qualifying
word (QUALIFIERS) is looked for outside its field's `not_a_qualifier` phrases ('closed until further notice'), which
are themselves never a reading.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

SEEDS = Path(__file__).resolve().parent.parent / "dbt" / "seeds"
FIELDS = ("status", "category", "title", "narrative")
#: The readings that qualify a closing word in the same field, the model's `hits` CTE's list.
QUALIFIERS = frozenset({"partly", "a_way_around", "not_a_closure", "states_a_start"})


def seed(name: str) -> list[dict]:
    with (SEEDS / f"{name}.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def words_of(value: str) -> str:
    """A value's words as the model's `padded_value` holds them: lowercase, one space between, one each side."""
    text = re.sub(r"\bnon[^a-z0-9]+", "non", value.lower())
    return " " + re.sub(r"[^a-z0-9]+", " ", text).strip() + " "


def unqualified(field: str, padded: str) -> str:
    """A padded value with its field's `not_a_qualifier` phrases taken out (the model's `qualifier_value`)."""
    for row in seed("notice_words"):
        if row["reads_as"] == "not_a_qualifier" and field in row["read_in"].split():
            padded = padded.replace(f" {row['word']} ", " ")
    return padded


def readings(field: str, value: str, *, states_only_codes: bool = True) -> set[tuple[str, str]]:
    """Every (reads_as, word) of the vocabulary that `value` holds in `field`. `states_only_codes` is whether every
    status the value's source states is a `code` word or an `unspecified` one, which a `code` row needs (the model's
    `source_statuses`)."""
    found = set()
    whole = value.strip().lower()
    padded = words_of(value)
    masked = unqualified(field, padded)
    for row in seed("notice_words"):
        if field not in row["read_in"].split() or row["reads_as"] == "not_a_qualifier":
            continue
        word = row["word"]
        if row["matches"] == "exact":
            hit = whole == word
        elif row["matches"] == "code":
            hit = whole == word and states_only_codes
        else:
            hit = f" {word} " in (masked if row["reads_as"] in QUALIFIERS else padded)
        if hit:
            found.add((row["reads_as"], word))
    return found


def reads_as(field: str, value: str, **kwargs) -> set[str]:
    return {reading for reading, _ in readings(field, value, **kwargs)}


def layer_name(name: str) -> str:
    """A layer's own name as the model reads it in its `layer` field: a capital after a small letter starts a word,
    so 'TemporaryClosure' reads as 'Temporary Closure' (the model's `field_values`)."""
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", name)


def layer_closes(name: str) -> bool:
    """Whether a layer's own name says closures as the model's c3 needs it: a closing word no qualifying word
    (QUALIFIERS) in the same name qualifies."""
    found = reads_as("layer", layer_name(name))
    return "closes_trail" in found and not found & QUALIFIERS
