// One notice, in every severity (#1373, the flow review's Notice component).
//
// Today, step 3, the Plan tab and the volunteer list each had a card of their
// own for "here is a thing you should know, and here is what to do about it":
// Today's closure/warning/advisory cards, the download card, the workday
// list's two honest absences. Same shape, four stylesheets. This is the one
// shape, and the rule the review attaches to it is the part worth keeping:
// EVERY NOTICE CARRIES ITS NEXT STEP. A warning with nothing to press is a
// dead end; "The topo sheet is not on this phone" with Download beside it is
// not.
//
// Three tones and they mean three things, never one thing at three volumes:
//
//   quiet   a fact with no urgency - "Couldn't check", the workday list
//           needing signal it has not had yet.
//   warn    something a hiker should act on before it matters - a stretch
//           not yet on the phone, a blowdown on tomorrow's walk.
//   urgent  something on the trail itself - a closure crossing a day. Drawn
//           with the danger role, which is the serious-warning red by day
//           and its lighter form on ink (tokens/colors.css), never a base
//           colour of its own.
//
// The action and the link are BUTTONS, not anchors: nothing here navigates by
// URL (App.tsx has no router, #970), and a 44px target is what a cold thumb
// needs. Either is omitted rather than disabled - a refusal is a sentence in
// the body, never a greyed control (D10).

import './notice.css'

export type NoticeTone = 'quiet' | 'warn' | 'urgent'

export interface NoticeProps {
  tone?: NoticeTone
  title: string
  /** The sentence under the title. A string, or a node when a caller has
   *  to carry a figure formatted elsewhere inside it. */
  body?: React.ReactNode
  /** The next step, drawn at the notice's edge: "Download", "Retry". */
  action?: { label: string; onClick: () => void }
  /** A door under the body, in the notice's own words: "Put the detour in
   *  day 5 ›". A second next step rather than a second action, for the
   *  urgent tone where the action is the thing and the link is the
   *  detail. */
  link?: { label: string; onClick: () => void }
  className?: string
}

export function Notice({
  tone = 'quiet',
  title,
  body,
  action,
  link,
  className,
}: NoticeProps) {
  return (
    <div
      className={['notice', `notice--${tone}`, className].filter(Boolean).join(' ')}
      // Warnings and closures announce themselves once, when they appear;
      // a quiet fact does not interrupt whatever a screen reader is reading.
      role={tone === 'quiet' ? undefined : 'status'}
    >
      <div className="notice__text">
        <p className="notice__title">{title}</p>
        {body !== undefined && body !== null && <p className="notice__body">{body}</p>}
        {link !== undefined && (
          <button type="button" className="notice__link" onClick={link.onClick}>
            {link.label}
          </button>
        )}
      </div>
      {action !== undefined && (
        <button type="button" className="notice__action" onClick={action.onClick}>
          {action.label}
        </button>
      )}
    </div>
  )
}
