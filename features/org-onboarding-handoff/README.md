# The organization-onboarding design handoff, as it was given

Source material, not a design of ours. These are the files the maintainer
handed over with #1539–#1542 and #762/#763, kept here so the question "does
what shipped match what was asked for" has something to check against.

**[ORG_ONBOARDING.md](../ORG_ONBOARDING.md) is still the design's one home.**
It is what the code follows and what moves when a decision changes. This
folder is the record of the starting point, and it does not get edited to
match what was built — a handoff that gets corrected after the fact stops
being evidence of anything.

## What is here, and what is not

| | |
| --- | --- |
| `SPEC.md` | The argument: the five rules every screen assumes, the decisions with their reasoning, the six conflicts with the existing backend, and the handoff's own known gaps. 344 lines. |
| `HANDOFF_README.md` | The map: 23 screens across five surfaces, the fidelity statement, and which parts of the repo each surface belongs in. |
| `copy/*.txt` | 27 per-screen extracts of the prototype's **rendered text**, captured from the handoff's own HTML mock-up in a real browser. One file per screen, named for the screen. |

**The rendered prototypes are not here**, deliberately: `Join Us.dc.html` and
`JoinUsShot.dc.html` are about 540KB each, and the bundle with its screenshots
and design-system files runs to roughly 1.3MB. A commit is a publication that
cannot be retracted ([.github/tests/test_no_committed_data.py](../../.github/tests/test_no_committed_data.py)
carries that argument in full for data), and 60KB of text answers the
questions that actually get asked — what did the design say, and in what
words. The maintainer holds the originals.

So `copy/*.txt` is what a comparison reads. It carries the sentences and not
the layout, which is the honest limit of what is kept here: a question about
spacing, or about which of two blocks came first, is not answerable from this
folder.

## The mock organization is not ours

The prototype runs on an invented organization — Ramapo Trail Conference, with
invented people (Maria Alvarez, Sam Ortiz), invented mile markers and invented
counts. Every name and number in `copy/` is theirs rather than a fact about
any real club, and a line here matching nothing in the built app is usually
that, not a gap. The four gaps the first comparison did find are recorded in
[ORG_ONBOARDING.md](../ORG_ONBOARDING.md) and in #1547's own history.

## What has been checked against this, and what has not

**Copy only, so far.** The first pass compared rendered sentences phrase by
phrase and skipped every line under 25 characters — which is every button
label, every field label and every count pill. It scored 13 of the 23
screens. Controls, block order, the states each screen draws, the count
numbers, design-token adherence, the four embeds and the four 390px phone
designs were not compared at all.
