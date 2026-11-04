# Kickoff prompt for Claude Code

Paste the block below as the first message of a Claude Code session in the OurHike repo,
after this folder has been added at `features/structure-inventory-handoff/`. It asks for the
design doc and the issues first, and no code until the maintainer has read both — the same
order the org-onboarding handoff took, and the one `CLAUDE.md` asks for ("Before any code,
the plan is drawn").

---

```
Read CLAUDE.md, CONTRIBUTING.md and BRANCHING.md first, then everything in
features/structure-inventory-handoff/: HANDOFF_README.md is the map, SPEC.md is the
argument, ISSUES.md is the phased list, fieldGuide.json and icons.json are content,
copy/*.txt is each screen's rendered text, plates_manifest.json is the licensed
photograph found for each field-card plate, plates/ are the three finished ones, and
tools/ is the house treatment and the fetch-review-treat script. The design references themselves (the 36 artboards and the walkthrough)
are not in the tree; I hold them and will share screenshots when you ask.

Then, before any code:

1. Write features/STRUCTURE_INVENTORY.md — the one home for this design, in the voice and
   shape of features/FIELD_NOTES.md and features/VOLUNTEERING.md: companion links, a scope
   line, the problem stated plainly, the six rules every screen assumes, the data model,
   permissions, the packaging ("a second front door" — SPEC.md §Packaging), what it
   refuses, open questions, and an evidence grade on every number (measured / reasoned /
   @unvalidated, with what would settle it). Carry the six conflicts from SPEC.md and their
   resolutions into it; where SPEC.md says a decision is mine, write it as an open question
   and stop. Do not enumerate tasks in the doc.

2. Open the Phase 1 and Phase 2 issues from ISSUES.md as GitHub issues, titles as written
   (they are meant to be read without opening), each body linking the design doc, carrying
   its acceptance line and the suites it touches, and ending with nothing else. Phase 3–5
   issues too, labelled by phase. Do not claim any of them yet.

3. Send me the two Phase 0 questions with the poll tool and a picture: the area unit
   (sections as areas for v1) with the Coverage screen beside a drawing of what the map
   would colour, and the Local Chair mapping (admin seat or named role) with the review
   queue header. I will answer both; nothing in Phase 1 starts before I have.

When I have answered: claim issue 1 with a comment naming the branch, one branch per issue
(BRANCHING.md), run scripts/test.sh before every push, scripts/pipelines.sh before every
pull request, a ## Screenshot section on every PR with a preview-shots recipe for every
screen a volunteer can reach, and never merge into main or cut a release. Build Phase 1 in
order; Phase 2 starts with issue 11 (the second front door) and issue 14 (the readings
screen), which are the two things in this design that do not exist anywhere in the client
yet, so their first screenshots come to me before the rest of Phase 2 is written. Issue 18
(the plates) can run any time in parallel: it is the one task that needs the open network
this session has and the design workspace did not. Its rule is the eye against the
caption — approve a photograph only when it shows exactly the scenario the caption names,
and send me the contact sheets with your approvals marked before treating anything.

Two standing rules from the design that are easy to lose while building:
- A volunteer's estimate is never rendered in the voice of a measurement — size_method
  travels with every size, all the way to the CSV.
- The phone never shows a presumed place. The readings screen is a grid, a scale bar and
  dots; the mile and the distance to the line are computed on the server after upload.
```

---

What the maintainer does in the meantime: answers the seven items in `SPEC.md` §"Before this
goes to Claude Code" (the two blocking ones first), and starts collecting the photographs on
the Field Guide doc's shot list — 77 plates are waiting on them.
