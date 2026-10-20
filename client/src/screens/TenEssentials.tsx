// The Ten Essentials page (#1689): a checklist first, and each line a door
// to REI's category page for it.
//
// The shape was chosen by the maintainer from a rendered mock (poll,
// 2026-09-26): reached from a "Before you go" row on the Plan tab (frame A),
// one list per hiker rather than per hike, and a tap on "REI ↗" goes straight
// to the browser with the banner above the list as the only disclosure
// (frame D). lib/tenEssentials.ts has why each of those is what it is, and
// where the tracking starts.

import {
  REI_AFFILIATE_LINK,
  TEN_ESSENTIALS,
  reiLink,
  type EssentialId,
} from '../lib/tenEssentials'
import type { PlanRoom } from '../lib/planRoom'
import './tenEssentials.css'

export interface TenEssentialsProps {
  /** Which room's band to wear, so the page reads as part of the room it was
   *  opened from. */
  room: PlanRoom
  packed: ReadonlySet<EssentialId>
  onChange: (packed: ReadonlySet<EssentialId>) => void
  onBack: () => void
  /** The affiliate deep link, or null for none. Defaults to what this build
   *  ships (lib/tenEssentials.ts); a prop so the tests can hold both
   *  banners without shipping a code. */
  affiliateTemplate?: string | null
}

export function TenEssentials({
  room,
  packed,
  onChange,
  onBack,
  affiliateTemplate = REI_AFFILIATE_LINK,
}: TenEssentialsProps) {
  const affiliate = affiliateTemplate !== null
  const toggle = (id: EssentialId) => {
    const next = new Set(packed)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onChange(next)
  }

  return (
    <div className="essentials">
      <header
        className={
          room === 'day' ? 'plan__head plan__head--day' : 'plan__head plan__head--trips'
        }
      >
        <button type="button" className="plan__crumb" onClick={onBack}>
          <span className="plan__crumb-up">&lsaquo; Plan</span>
        </button>
        <h1 className="plan__title">The Ten Essentials</h1>
      </header>

      {/* THE ONLY DISCLOSURE, so it heads the page rather than trailing it
          (frame D). It says what a tap does before any tap is made. Which
          sentence it carries follows the build: no affiliate code, no claim
          of a commission. */}
      <p className="essentials__disclose" role="note">
        {affiliate ? (
          <>
            <strong>Links on this page go to REI.</strong> If you buy something there,
            OurHike earns a commission. Each link opens in your browser, and nothing is
            tracked until you tap one.
          </>
        ) : (
          <>
            <strong>Links on this page go to REI.</strong> Each one opens in your browser.
          </>
        )}
      </p>

      <ul className="essentials__list">
        {TEN_ESSENTIALS.map((essential) => {
          const inputId = `essential-${essential.id}`
          return (
            <li className="essentials__item" key={essential.id}>
              <input
                id={inputId}
                className="essentials__check"
                type="checkbox"
                checked={packed.has(essential.id)}
                onChange={() => toggle(essential.id)}
              />
              <label className="essentials__label" htmlFor={inputId}>
                <span className="essentials__name">{essential.name}</span>
                <span className="essentials__note">{essential.note}</span>
              </label>
              <a
                className="essentials__shop"
                href={reiLink(essential, affiliateTemplate)}
                target="_blank"
                rel="noreferrer"
                aria-label={`Shop ${essential.shopFor} at REI`}
              >
                REI <span aria-hidden="true">↗</span>
              </a>
            </li>
          )
        })}
      </ul>

      <div className="essentials__foot">
        <p className="plan-home__quiet-note">
          {/* Said because it is not obvious: a hiker on a second hike sees the
              ticks from the first one until they clear them. */}
          Your ticks stay on this phone and show on every hike.
        </p>
        {packed.size > 0 && (
          <button
            type="button"
            className="plan-home__all"
            onClick={() => onChange(new Set())}
          >
            Clear all ticks
          </button>
        )}
      </div>
    </div>
  )
}
