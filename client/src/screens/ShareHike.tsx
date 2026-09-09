// Sharing a finished hike (#1317), following features/COMMUNITY_BUILDING.md
// exactly.
//
// TWO WAYS, AND THEY HAND OVER DIFFERENT THINGS. One grants another ACCOUNT
// read access to the hike, in their own app - mutual, revocable, and gone
// the moment it is taken back. The other is a plain-text card that anybody
// can read, and it is a snapshot: once it has left, it cannot be revoked,
// which is exactly why it holds figures and dates and nothing else.
//
// THERE IS NO PUBLIC LINK, ON PURPOSE. COMMUNITY_BUILDING.md's own line: "a
// leaked link would mean anyone, not just someone chosen" can see it. That
// document made the call for live location and the reasoning carries here -
// a hike names every place somebody sleeps, which is a route somebody could
// meet them on. So the refusal is on the screen rather than only in the doc,
// because a hiker looking for a "copy link" button is owed the reason it is
// not there rather than the impression the feature is unfinished.
//
// NEITHER SHARES WHERE THE HIKER IS. Live location is its own opt-in, per
// session, with its own unmistakable indicator, and a shared hike must never
// become a quiet second channel for it. That separation is the whole reason
// both features can exist.

import { useState } from 'react'

import type { UnitSystem } from '../lib/units'
import './plan.css'

export interface HikeShareRecipient {
  id: string
  name: string
  state: 'shared' | 'invited'
}

export interface ShareHikeProps {
  hikeName: string
  /** The card, from `lib/hikeShareText.ts` - one derivation, so the preview
   *  and what is actually copied cannot differ. */
  cardText: string
  recipients: readonly HikeShareRecipient[]
  units: UnitSystem
  onInvite: () => void
  onClose: () => void
  /** Injectable for tests; defaults to the real navigator. */
  share?: (text: string) => Promise<void>
  canShare?: boolean
}

type HandOver = 'idle' | 'shared' | 'share-failed' | 'copied' | 'copy-failed'

export function ShareHike({
  hikeName,
  cardText,
  recipients,
  onInvite,
  onClose,
  share,
  canShare = typeof navigator !== 'undefined' && 'share' in navigator,
}: ShareHikeProps) {
  const [handOver, setHandOver] = useState<HandOver>('idle')

  const sendIt = async () => {
    try {
      if (share !== undefined) await share(cardText)
      else await navigator.share({ text: cardText })
      setHandOver('shared')
    } catch {
      // A cancelled share sheet lands here too, and telling somebody who
      // changed their mind that it "failed" would be wrong - so this points
      // at the copy path (LeaveWithSomeone.tsx's rule).
      setHandOver('share-failed')
    }
  }

  const copyIt = async () => {
    try {
      await navigator.clipboard.writeText(cardText)
      setHandOver('copied')
    } catch {
      setHandOver('copy-failed')
    }
  }

  return (
    <div className="share-hike" role="dialog" aria-label="Share this hike">
      <div className="legend__head">
        <h2 className="legend__title">Share this hike</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <p className="plan-kind__lede">
        Two ways, and they hand over different things. Neither shares where you are — live
        location is its own opt-in, per session, and it isn&rsquo;t this.
      </p>

      <section
        className="share-hike__section"
        aria-label="With a hiker you’re connected to"
      >
        <h3 className="plan-home__title">With a hiker you&rsquo;re connected to</h3>
        <p className="share-hike__note">
          They get read access to {hikeName} — its sections, days and figures, in their
          own app. Mutual only: they have to accept, and you can take it back.
        </p>
        {recipients.map((person) => (
          <div className="route-stops__field share-hike__person" key={person.id}>
            <span className="route-stops__name">{person.name}</span>
            <span className="route-stops__mile">
              {person.state === 'shared' ? 'shared · can see it' : 'invited · waiting'}
            </span>
          </div>
        ))}
        <button type="button" className="route-stops__add" onClick={onInvite}>
          <span>Invite someone</span>
          <span aria-hidden="true">+</span>
        </button>
        <p className="plan-home__refused">
          There is no public link, on purpose. A link that reaches anybody reaches people
          you didn&rsquo;t choose.
        </p>
      </section>

      <section className="share-hike__section" aria-label="With anyone else">
        <h3 className="plan-home__title">With anyone else</h3>
        <p className="share-hike__note">
          A plain-text card. It survives a phone with no OurHike on it — and once it has
          left, it cannot be taken back.
        </p>
        <pre className="share-hike__preview">{cardText}</pre>

        {/* Only where Web Share exists. A control that looks pressable and is
            not teaches a hiker the app is broken (LineSheet's rule), and on a
            desktop browser the honest offer is the copy button alone. */}
        {canShare && (
          <button type="button" className="plan__primary" onClick={() => void sendIt()}>
            Send it
          </button>
        )}
        <button type="button" className="today__action" onClick={() => void copyIt()}>
          Copy as plain text
        </button>

        {handOver !== 'idle' && (
          <p className="share-hike__status" role="status">
            {handOver === 'shared'
              ? 'Sent.'
              : handOver === 'copied'
                ? 'Copied.'
                : handOver === 'share-failed'
                  ? 'Not sent — you can copy it instead.'
                  : 'Could not copy — select the card above and copy it by hand.'}
          </p>
        )}
      </section>
    </div>
  )
}
