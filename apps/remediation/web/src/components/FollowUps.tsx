import type { FollowUp } from '../api'
import { FOLLOW_UP_LABEL } from '../claims'

// A follow-up's dates are days, not moments: shown as written, in UTC, so a
// browser west of Greenwich does not move Sep 7 to Sep 6.
const day = new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeZone: 'UTC' })
const asDay = (date: string) => day.format(new Date(`${date}T00:00:00Z`))

/**
 * A restored site's three follow-up visits (PLAN.md §6): each opens the day
 * after Labor Day, and anyone may take an open one for 14 days.
 */
export function FollowUpList({
  followUps,
  onTake,
}: {
  followUps: FollowUp[]
  onTake?: (followUp: FollowUp) => void
}) {
  return (
    <section
      className="card"
      aria-labelledby="follow-ups"
      style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
    >
      <h2 id="follow-ups" className="eyebrow">
        Follow-up visits
      </h2>
      <p className="muted" style={{ margin: 0 }}>
        One after each of the next three peak seasons: re-photograph both points, and put
        the cover back if it has moved. Each opens the day after Labor Day; anyone may
        take it, for 14 days.
      </p>
      <ol
        style={{
          margin: 0,
          paddingLeft: 20,
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
        }}
      >
        {followUps.map((f) => (
          <li key={f.id}>
            <b>Visit {f.visit}</b> · opens {asDay(f.opens_on)} ·{' '}
            {FOLLOW_UP_LABEL[f.state]}
            {f.state === 'open' && (
              <>
                {' '}
                <span className="muted">until {asDay(f.closes_on)}</span>{' '}
                {onTake && (
                  <button
                    type="button"
                    className="button primary"
                    onClick={() => onTake(f)}
                  >
                    Take visit {f.visit}
                  </button>
                )}
              </>
            )}
          </li>
        ))}
      </ol>
    </section>
  )
}
