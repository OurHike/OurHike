#!/usr/bin/env python3
"""A poll to the maintainer carries a picture, or says why it cannot (#1566).

WHAT THIS IS. Two hooks in one file, so the sentence they both say has one home:

    visual_poll.py check    PostToolUse on AskUserQuestion. After a poll has gone
                            out, look at what it carried; when there was no
                            picture and no `No visual:` line, hand the session one
                            paragraph saying so (hookSpecificOutput.additionalContext).
    visual_poll.py remind   SessionStart (startup, resume, compact). One line saying
                            the rule exists and where the how is.

WHY IT LETS THE POLL THROUGH. The maintainer chose this over a hook that refuses
the poll (poll, 2026-09-17, on #1566 - A session's questions to the maintainer
carry no wireframe or screenshot, so the plan cannot be seen from the words): the
question still reaches them, and the session is told afterwards. So `check`
never blocks, never exits non-zero on a verdict, and on its own bug says nothing
rather than failing a poll that has already been answered - see check().

WHAT COUNTS AS A PICTURE. Any one of three things:

  1. an option with a non-empty `preview` - a drawing inside the poll, the
     fallback for a session with no side panel;
  2. a question that names a file the session sent to the side panel first
     (something.html / .png / .svg / .jpg / .pdf) - because a picture the
     maintainer has to hunt for is half a picture, and the name is what tells
     them which panel to look at;
  3. the line `No visual: <why>` in a question - the honest answer for a choice
     with nothing to draw, the same words the pull request template's
     `## Screenshot` section accepts. The reason is the part that counts.

Stateless by design: it reads only the poll. It cannot see whether the named
file was really sent and does not try - the maintainer sees an empty panel and
says so, and this is a reminder rather than a gate (their choice above).

EVIDENCE GRADE. That PostToolUse fires for `AskUserQuestion` with the poll's
`questions` under `tool_input` is reasoned from the hooks documentation (a
matcher is a regex on the tool name; `tool_input` is the tool's input object),
not yet observed from inside a session. The first session to see the paragraph
below in its context should say so on #1566, and this sentence can then change.
.github/tests/test_visual_poll_hook.py holds the rest.
"""

from __future__ import annotations

import json
import re
import sys

SKILL = ".claude/skills/visual-poll/SKILL.md"
ISSUE = (
    "#1566 - A session's questions to the maintainer carry no wireframe or screenshot, so the plan cannot be seen from the words"
)

# A file the session sent to the side panel, named in the question. These are
# the extensions SendUserFile renders inline; a .mjs or .py named in a question
# is code, not a picture.
PICTURE_FILE = re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.(?:html?|png|svg|jpe?g|gif|webp|pdf)\b", re.IGNORECASE)

# The reason is the part that counts: a bare `No visual:` is not an answer.
NO_VISUAL = re.compile(r"\bno visual:\s*\S", re.IGNORECASE)

REMINDER = (
    f"Visual polls ({ISSUE}): a choice about anything a hiker sees goes to the maintainer as a poll "
    "with a picture - a rendered mock or a screenshot sent to the side panel first (SendUserFile, "
    "display render) and named in the question - before any code, after the first build, and at "
    "every fork; a choice with nothing to draw says `No visual: <why>` in the question. "
    f"How: {SKILL}. An unattended (night-shift) session does not poll at all."
)


def _texts(questions) -> list[str]:
    """Every string a poll shows the maintainer, so the file name may sit in any of them."""
    out = []
    for question in questions or []:
        if not isinstance(question, dict):
            continue
        for key in ("question", "header"):
            if isinstance(question.get(key), str):
                out.append(question[key])
        for option in question.get("options") or []:
            if not isinstance(option, dict):
                continue
            for key in ("label", "description"):
                if isinstance(option.get(key), str):
                    out.append(option[key])
    return out


def _previews(questions) -> list[str]:
    return [
        option["preview"]
        for question in questions or []
        if isinstance(question, dict)
        for option in question.get("options") or []
        if isinstance(option, dict) and isinstance(option.get("preview"), str) and option["preview"].strip()
    ]


def verdict(questions) -> tuple[bool, str]:
    """Whether the poll carried a picture, and the sentence saying which - or which it lacked."""
    if _previews(questions):
        return True, "an option carries a preview"
    texts = _texts(questions)
    for text in texts:
        found = PICTURE_FILE.search(text)
        if found:
            return True, f"the question names {found.group(0)}"
    if any(NO_VISUAL.search(text) for text in texts):
        return True, "the question says `No visual:` and why"
    return (
        False,
        "no option has a `preview`, no question names a file sent to the side panel "
        "(.html, .png, .svg, .jpg, .pdf), and none says `No visual: <why>`",
    )


def nag(why: str) -> str:
    return (
        f"The poll just asked carried no picture: {why}. The maintainer's standing ask ({ISSUE}; "
        "poll 2026-09-17: let it through, tell the session afterwards) is a rendered mock or a "
        "screenshot in the side panel before every poll about something a hiker sees. Before the next "
        "poll: write the mock or take the screenshot, send it with SendUserFile (display render), and "
        f"name its file in the question - or write the one-line `No visual: <why>` answer. How: {SKILL}."
    )


def check(stdin) -> str | None:
    """The PostToolUse half: the JSON to print, or None to say nothing."""
    try:
        event = json.load(stdin)
    except ValueError:
        # Unreadable input: say nothing rather than fail a poll the maintainer
        # has already seen.
        return None
    if not isinstance(event, dict) or event.get("tool_name") != "AskUserQuestion":
        return None
    tool_input = event.get("tool_input")
    questions = tool_input.get("questions") if isinstance(tool_input, dict) else None
    ok, why = verdict(questions)
    if ok:
        return None
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": nag(why)}})


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else ""
    if mode == "remind":
        print(REMINDER)
        return 0
    if mode == "check":
        out = check(sys.stdin)
        if out is not None:
            print(out)
        return 0
    print("usage: visual_poll.py check|remind", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
