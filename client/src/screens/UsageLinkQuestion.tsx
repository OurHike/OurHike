// "Link your usage to your account?" - asked once, after a sign-in (#1902,
// features/EVENTING.md §0).
//
// The wording is the maintainer's choice, approved as drawn (poll 2026-10-27,
// frame C of the mock page), and three of its sentences carry promises the
// rest of the build has to keep:
//
//   - "No name or email goes with it" - the server stores a keyed hash of the
//     account (`user_key`) and the account id only sealed, never in the clear
//     (backend/app/routers/analytics.py).
//   - "Your position goes with each count either way" - true because sending
//     a position only on a yes was declined (poll 2026-10-27, package 4). The
//     question must not let "No thanks" read as stopping location; only the
//     Safety & privacy switch does that, and the last line says where it is.
//   - "Counts are deleted after six months" - backend/app/core/
//     analytics_rollup.py - and "a running total for your account until you
//     unlink or delete it", the User table, which a no or a deletion removes
//     (routers/preferences.py, core/account_deletion.py).
//
// TWO SENTENCES HERE WERE CORRECTED after #1903's review found them stronger
// than the code: "sealed so our servers cannot read it" (the server keeps the
// 0.1-degree square in the clear, beside the code for a yes) and "everything
// is deleted after six months" (the running total is not). The maintainer
// approved the corrected wording in a poll on 2026-10-27, against before and
// after frames of this screen and Safety & privacy.
//
// Either answer leads back to where the hiker was. Nothing is asked again:
// the answer is `measurement_linked`, synced, so a second phone does not ask.

import './reporting.css'
import './usageLink.css'

export interface UsageLinkQuestionProps {
  onAnswer: (linked: boolean) => void
}

export function UsageLinkQuestion({ onAnswer }: UsageLinkQuestionProps) {
  return (
    <main className="reporting usage-link">
      <h1 className="reporting__title">Link your usage to your account?</h1>
      <p className="usage-link__body">
        OurHike already counts what gets used, with no name attached. Saying yes adds a
        code made from your account, so we can see whether hikers come back and finish the
        hikes they plan.
      </p>
      <ul className="usage-link__points">
        <li>No name or email goes with it.</li>
        <li>
          Your position goes with each count <strong>either way</strong> while location is
          on, sealed as it arrives. Only the rough area it falls in, a grid square about
          the size of a town, stays readable, and beside the code if you say yes.
        </li>
        <li>
          Counts are deleted after six months. Saying yes also keeps a running total for
          your account until you unlink or delete it.
        </li>
      </ul>
      <p className="usage-link__minor">
        To stop sharing entirely: More → Safety &amp; privacy → Share usage statistics.
      </p>
      <div className="reporting__actions usage-link__actions">
        <button
          type="button"
          className="reporting__primary"
          onClick={() => onAnswer(true)}
        >
          Yes, link it
        </button>
        <button
          type="button"
          className="reporting__secondary"
          onClick={() => onAnswer(false)}
        >
          No thanks
        </button>
      </div>
    </main>
  )
}
