/**
 * The four screens where the work actually gets logged.
 *
 * **THESE ARE A SEPARATE DESIGN, NOT THE DESKTOP SCREENS MADE NARROW.** A
 * maintainer standing at a blowdown and a supervisor in a trailhead car park
 * need different things from an admin at a laptop - fewer of them, bigger,
 * and working with no signal. Rendering the console at 390px would produce a
 * screen that technically fits and that nobody can use in the cold.
 *
 * Four rules, and every frame below obeys all four:
 *
 * - **One job per screen.** No tabs, no side panels. If it is not the thing
 *   you came to do, it is not here.
 * - **Everything works offline.** Actions queue and sync later; a screen never
 *   blocks on a network it does not have. This is the rule the other three
 *   exist to protect - an app that needs a bar of signal to record a blowdown
 *   records no blowdowns.
 * - **Hit targets 44px and up.** Gloves, low sun, one hand on a trekking pole.
 * - **Never type what we can read.** Location, time and section come from
 *   where the phone already is, so the three-tap report is three taps.
 *
 * **A PARK ALERT APPEARS HERE AND IS NOT CLOSEABLE HERE EITHER.** The frame
 * says "not yours to close" in as many words, for the reason `YourTread.tsx`
 * gives at length: a volunteer who can clear a land manager's closure can put
 * a hiker through a bridge that is out.
 *
 * This page is a gallery of those four on a desktop screen - what a club
 * admin reads to find out what their volunteers will actually see. The frames
 * are static renderings of real components' copy, not live screens; a phone
 * reaches the real ones through the app.
 */

import { PageHeader, PhoneFrame } from '../components'

export interface PhoneReportQueue {
  readonly queued: number
  readonly online: boolean
}

export interface OnYourPhoneProps {
  readonly sectionName: string
  readonly range: string
  readonly openReports: number
  readonly thanksCount: number
  readonly queue: PhoneReportQueue
  readonly downloadedOn: string | null
  /** A land manager's alert on these miles, when there is one. */
  readonly parkAlert: { readonly title: string; readonly detail: string } | null
  readonly crewHours: {
    readonly people: number
    readonly hours: number
    readonly waiting: number
  }
  readonly poisNearby: number
}

const RULES: readonly { title: string; body: string }[] = [
  {
    title: 'One job per screen.',
    body: 'No tabs, no side panels. If it is not the thing you came to do, it is not here.',
  },
  {
    title: 'Everything works offline.',
    body: 'Actions queue and sync later. A screen never blocks on a network it does not have.',
  },
  {
    title: 'Hit targets 44px and up.',
    body: 'Assume gloves, low sun and one hand on a trekking pole.',
  },
  {
    title: 'Never type what we can read.',
    body: 'Location, weather and section come from where the phone already is.',
  },
]

export function OnYourPhone({
  sectionName,
  range,
  openReports,
  thanksCount,
  queue,
  downloadedOn,
  parkAlert,
  crewHours,
  poisNearby,
}: OnYourPhoneProps) {
  return (
    <>
      <PageHeader
        eyebrow="In the field · phone, one bar, cold hands"
        title="Where the work actually gets logged"
        sub={
          <>
            Not the desktop screens made narrow. A maintainer standing at a blowdown and a
            supervisor in a trailhead car park need different things than an admin at a
            laptop — fewer of them, bigger, and working with no signal.
          </>
        }
        glyph={
          <>
            <rect x="7" y="2.5" width="10" height="19" rx="2.5" />
            <path d="M10.5 18.5h3" />
          </>
        }
      />

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Rules these four follow</h2>
        </div>
        <div className="org-grid org-grid--two">
          {RULES.map((rule) => (
            <div className="org-tile" key={rule.title}>
              <span className="org-tile__label">{rule.title}</span>
              <span className="org-tile__meta">{rule.body}</span>
            </div>
          ))}
        </div>
      </section>

      <div className="org-phones">
        <PhoneFrame
          label="Your tread · maintainer, offline"
          note={
            downloadedOn
              ? `Downloaded ${downloadedOn} · works with no signal`
              : 'Not downloaded yet — this screen still opens, with what it last knew.'
          }
        >
          <div className="org-phone__bar">
            <span>9:41</span>
            <span>
              {queue.online ? 'Online' : 'No signal'}
              {queue.queued > 0
                ? ` · ${queue.queued} ${queue.queued === 1 ? 'report' : 'reports'} queued`
                : ''}
            </span>
          </div>
          <div className="org-phone__row">
            <span className="org-eyebrow">Your tread</span>
            <p className="org-table__name">{sectionName}</p>
            <p className="org-mono">{range}</p>
          </div>
          {openReports > 0 ? (
            <div className="org-phone__row">
              <p className="org-table__name">
                {openReports} open {openReports === 1 ? 'report' : 'reports'} on your
                miles
              </p>
              <p className="org-mono">Read them before you go out.</p>
              <span className="org-btn org-btn--ghost org-btn--small">Read both</span>
            </div>
          ) : null}
          <div className="org-phone__row">
            <span className="org-btn">Report something</span>
            <span className="org-btn org-btn--ghost">Log hours</span>
            <span className="org-btn org-btn--ghost">Check a POI</span>
          </div>
          {thanksCount > 0 ? (
            <div className="org-phone__row">
              <p className="org-table__name">
                {thanksCount} {thanksCount === 1 ? 'thanks' : 'thanks'} on your miles
              </p>
              <p className="org-mono">Left by hikers. No names, theirs or yours.</p>
            </div>
          ) : null}
          {parkAlert ? (
            <div className="org-phone__row">
              <p className="org-table__name">Park alert · not yours to close</p>
              <p className="org-mono">{parkAlert.title}</p>
              <p className="org-mono">{parkAlert.detail}</p>
            </div>
          ) : null}
          <div className="org-phone__row">
            <span className="org-btn org-btn--ghost">Ask to close a stretch</span>
          </div>
        </PhoneFrame>

        <PhoneFrame
          label="Report something · three taps"
          note="The third tap sends it. Nothing on this screen has to be typed."
        >
          <div className="org-phone__bar">
            <span>9:41</span>
            <span>Cancel</span>
          </div>
          <div className="org-phone__row">
            <p className="org-table__name">What did you find?</p>
            <span className="org-btn">Blowdown</span>
            <span className="org-btn org-btn--ghost">Washout</span>
            <span className="org-btn org-btn--ghost">Missing blaze</span>
            <span className="org-btn org-btn--ghost">Something else</span>
          </div>
          <div className="org-phone__row">
            <span className="org-eyebrow">We filled these in</span>
            <p className="org-mono">📍 {range.split('·')[0]?.trim() || range}</p>
            <p className="org-mono">🕘 Today, 9:41am</p>
            <p className="org-mono">You are the maintainer here</p>
          </div>
          <div className="org-phone__row">
            <span className="org-btn org-btn--ghost">Add a photo</span>
            <p className="org-mono">Anything else worth saying? (optional)</p>
            <span className="org-btn">Send it</span>
          </div>
          <div className="org-phone__row">
            <p className="org-mono">
              No signal — this queues and goes on its own when you get back.
            </p>
          </div>
        </PhoneFrame>

        <PhoneFrame
          label="Confirm hours · supervisor"
          note="A figure you disagree with goes back to that person with your note, never quietly changed."
        >
          <div className="org-phone__bar">
            <span>9:41</span>
            <span>Saturday</span>
          </div>
          <div className="org-phone__row">
            <span className="org-eyebrow">Pine Meadow rock steps</span>
            <p className="org-table__name">Confirm the crew's hours</p>
            <p className="org-mono">
              {crewHours.people} people logged {crewHours.hours} hours. Confirm what you
              saw — the organization reports these onward.
            </p>
          </div>
          <div className="org-phone__row">
            <p className="org-mono">
              {crewHours.waiting} still waiting on you
              {crewHours.waiting === 0 ? ' — nothing to do here today' : ''}
            </p>
            <span className="org-btn">Confirm all {crewHours.people}</span>
          </div>
          <div className="org-phone__row">
            <p className="org-mono">
              Disagree with a figure? It goes back to that person with your note. An hour
              you decline to confirm stays on their record as claimed — it is theirs, not
              yours.
            </p>
          </div>
        </PhoneFrame>

        <PhoneFrame
          label="POI upkeep · standing at it"
          note="Your edits go live for hikers straight away. An admin sees them in their proposals queue and can roll one back."
        >
          <div className="org-phone__bar">
            <span>9:41</span>
            <span>
              {poisNearby} {poisNearby === 1 ? 'POI' : 'POIs'} near you
            </span>
          </div>
          <div className="org-phone__row">
            <p className="org-table__name">Is this still right?</p>
          </div>
          <div className="org-phone__row">
            <p className="org-table__name">Stone Shelter privy</p>
            <p className="org-mono">40m away · last checked Feb 2025</p>
            <p className="org-mono">
              Listed as usable, with a note that the door latch sticks.
            </p>
            <span className="org-btn">Still true</span>
            <span className="org-btn org-btn--ghost">Changed</span>
            <span className="org-btn org-btn--ghost">It's gone</span>
          </div>
          <div className="org-phone__row">
            <span className="org-btn org-btn--ghost">Add one that is missing</span>
          </div>
        </PhoneFrame>
      </div>

      <div className="org-callout" data-tone="info">
        <span>
          <strong>Offline is the default assumption, not a degraded mode.</strong> Every
          action on these four queues locally and sends when a signal arrives, dated to
          when it was written rather than when it sent. A report written at 9:41 in a
          hollow with no bars is a 9:41 report.
        </span>
      </div>
    </>
  )
}
