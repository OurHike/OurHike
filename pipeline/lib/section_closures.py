"""Which trail lines an organization's own closure notice closes by naming their section.

One general rule for every organization: nothing here names an organization, a trail or a line.

THE RULE. A notice closes a set of lines when all of these hold, and otherwise closes nothing:
- it is closing in its own words: `obstructs_trail` in conditions/notices.json, which the closures vocabulary
  (seeds/notice_words.csv) decides upstream;
- it carries no geometry of its own (`place.kind` is not `geometry`): a placed notice already draws its own extent,
  and closing every line of the same name could close more ground than the notice does;
- it names a section: its whole title, or a phrase of one to four words before the word "section" in it;
- exactly one line set carries that section's name as its whole name, where a line set is the network lines of one
  layer sharing one name, and a name written "<trail> - <section>" (USFS's "TUSCARORA - DOLL RIDGE") is matched on
  its section part, and only when the notice's title also names its trail part;
- the notice is the line's steward's (the same registry `provider`), or a club's that names the trail part.
Every comparison is on lowercase words, so punctuation and case never decide a match. Two or more line sets is
ambiguous and closes nothing; so does a section that no line set carries. evaluate() lists both, and
step_section_closures.py prints the list in every monthly build's log for a person to read.

WHY THIS STRICT (CLAUDE.md, "Miss rather than cry wolf"): measured 2026-10-15 over UA's release 2026-10-10-2, a
looser rule (a line name found anywhere inside a title) matched a notice titled "Bass River SF" to a New Jersey line
named "River", and "Boreas Pass Section House" to two USFS lines named "PASS". Whole names do not.

@unvalidated: the four-word cap on a section phrase and the generic words below are picked, not fitted; what would
settle them is the list step_section_closures.py prints, read by a person, over the next months' notices.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

#: Words that never make a name on their own: a section name of only these closes nothing.
GENERIC_WORDS = frozenset({"a", "and", "of", "the", "trail", "trails", "trl", "section", "path", "loop"})
#: The most words a "<name> section" phrase is read back over.
SECTION_PHRASE_WORDS = 4


def words(text: str | None) -> tuple[str, ...]:
    """Lowercase letters and digits, as both sides of every comparison read a name."""
    return tuple(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _named(name: tuple[str, ...]) -> bool:
    return any(word not in GENERIC_WORDS for word in name)


def _contains(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    return bool(needle) and any(haystack[i : i + len(needle)] == needle for i in range(len(haystack) - len(needle) + 1))


def section_names(title: str | None) -> set[tuple[str, ...]]:
    """What a notice's title names as a section: the whole title, and each phrase of one to SECTION_PHRASE_WORDS
    words before "section"."""
    title_words = words(title)
    names = {title_words}
    for i, word in enumerate(title_words):
        if word == "section":
            names.update(title_words[i - k : i] for k in range(1, SECTION_PHRASE_WORDS + 1) if i - k >= 0)
    return {name for name in names if _named(name)}


@dataclass(frozen=True)
class LineSet:
    """The network lines of one layer that share one name."""

    source_key: str
    name: str
    provider: str | None
    line_ids: tuple[str, ...]
    miles: float

    @property
    def trail(self) -> tuple[str, ...]:
        """The trail part of a "<trail> - <section>" name, its generic words left out; empty for any other name."""
        return tuple(w for w in words(self.name.partition(" - ")[0]) if w not in GENERIC_WORDS) if " - " in self.name else ()

    @property
    def section(self) -> tuple[str, ...]:
        return words(self.name.partition(" - ")[2]) if " - " in self.name else words(self.name)


def line_sets(lines, providers: dict[str, str]) -> list[LineSet]:
    """Group (line_id, source_key, name, miles) rows into LineSets; a line with no name is in none."""
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for line_id, source_key, name, miles in lines:
        if name and name.strip():
            groups[(source_key, name)].append((line_id, miles or 0.0))
    return [
        LineSet(source, name, providers.get(source), tuple(i for i, _ in rows), sum(m for _, m in rows))
        for (source, name), rows in sorted(groups.items())
    ]


@dataclass
class Outcome:
    """What the rule says of one notice. `verdict` is one of VERDICTS."""

    notice: dict
    verdict: str
    candidates: list[LineSet] = field(default_factory=list)
    section: str | None = None


#: closes: exactly one line set, and it closes. The rest close nothing and are listed for a person:
#: ambiguous (two or more sets), no_line (a "<name> section" phrase no set carries), not_closing (a notice whose
#: words would match but which does not close the trail), placed (a closing notice drawn by its own geometry).
VERDICTS = ("closes", "ambiguous", "no_line", "not_closing", "placed")


def evaluate(notices, sets: list[LineSet]) -> list[Outcome]:
    """Every notice the rule has something to say about, in the notices' order. A notice with no candidate set and
    no section phrase is left out: there is nothing to read."""
    by_section: dict[tuple[str, ...], list[LineSet]] = defaultdict(list)
    for line_set in sets:
        if _named(line_set.section):
            by_section[line_set.section].append(line_set)

    outcomes = []
    for notice in notices:
        title = words(notice.get("title"))
        candidates = []
        for name in section_names(notice.get("title")):
            for line_set in by_section.get(name, ()):
                if line_set.trail and not _contains(title, line_set.trail):
                    continue
                own = notice.get("provider") is not None and notice.get("provider") == line_set.provider
                clubs_trail = notice.get("steward_kind") == "club" and bool(line_set.trail)
                if (own or clubs_trail) and line_set not in candidates:
                    candidates.append(line_set)
        phrase = re.search(r"((?:[A-Z][\w'.-]*\s+){0,3}[A-Z][\w'.-]*)\s+[Ss]ection\b", notice.get("title") or "")
        closing = bool(notice.get("obstructs_trail"))
        if not candidates:
            if closing and phrase:
                outcomes.append(Outcome(notice, "no_line", section=phrase.group(1)))
            continue
        if not closing:
            verdict = "not_closing"
        elif (notice.get("place") or {}).get("kind") == "geometry":
            verdict = "placed"
        elif len(candidates) > 1:
            verdict = "ambiguous"
        else:
            verdict = "closes"
        outcomes.append(Outcome(notice, verdict, candidates))
    return outcomes
