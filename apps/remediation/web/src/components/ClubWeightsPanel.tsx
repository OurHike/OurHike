import { useState, type FormEvent } from 'react'
import type { ClubWeights, RemediationApi } from '../api'
import { sameWeights } from '../ranking'
import { WEIGHT_NAMES, type WeightName, type Weights } from '../types'

export const WEIGHT_LABEL: Record<WeightName, string> = {
  deficit: 'CSI shortfall',
  water: 'Near water',
  trail: 'Near the A.T.',
  cluster: 'In a cluster',
  restricted: 'Camping restricted',
}

const when = new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' })

function who(entry: { by_you: boolean; changed_by: string | null }): string {
  if (entry.by_you) return 'you'
  return entry.changed_by ?? 'a volunteer'
}

/** Edit a club's weights, and its history with restore (PLAN.md §8 `club_weights`). */
export function ClubWeightsPanel({
  api,
  weights,
  onChange,
}: {
  api: RemediationApi
  weights: ClubWeights
  onChange: (next: ClubWeights) => void
}) {
  const [draft, setDraft] = useState<Weights>(weights.current)
  const [note, setNote] = useState('')
  const [problem, setProblem] = useState<string | null>(null)

  const run = async (step: () => Promise<ClubWeights>) => {
    try {
      const next = await step()
      onChange(next)
      setDraft(next.current)
      setNote('')
      setProblem(null)
    } catch (error) {
      setProblem((error as Error).message)
    }
  }
  const save = (event: FormEvent) => {
    event.preventDefault()
    void run(() => api.changeWeights(weights.club, draft, note.trim() || null))
  }

  return (
    <section
      className="card"
      aria-label={`${weights.club}'s weights`}
      style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
    >
      <h2 style={{ fontSize: 20 }}>{weights.club}'s weights</h2>
      <p className="muted" style={{ margin: 0 }}>
        Anyone signed in can change these, and every change is kept below with who made
        it. They re-rank this club's sites for everyone signed in. Nobody has checked any
        set of weights against a club's own judgement yet.
      </p>
      <form
        onSubmit={save}
        style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end' }}
      >
        {WEIGHT_NAMES.map((name) => (
          <div className="field" key={name}>
            <label htmlFor={`w-${name}`}>{WEIGHT_LABEL[name]}</label>
            <input
              id={`w-${name}`}
              type="number"
              min={0}
              max={100}
              step={1}
              required
              value={draft[name]}
              onChange={(e) =>
                setDraft({ ...draft, [name]: Math.round(Number(e.target.value)) })
              }
              style={{ width: 96 }}
            />
          </div>
        ))}
        <div className="field" style={{ flex: '1 1 240px' }}>
          <label htmlFor="w-note">Why (optional)</label>
          <input
            id="w-note"
            maxLength={200}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>
        <button
          type="submit"
          className="button primary"
          disabled={sameWeights(draft, weights.current)}
        >
          Save weights
        </button>
        <button
          type="button"
          className="button"
          onClick={() => setDraft(weights.defaults)}
        >
          Start from the defaults
        </button>
      </form>
      {problem && (
        <p role="alert" style={{ margin: 0, color: '#8a3a14' }}>
          {problem}
        </p>
      )}
      <div>
        <h3 className="eyebrow" style={{ marginBottom: 6 }}>
          History
        </h3>
        {weights.history.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            Nobody has changed this club's weights. It ranks by the defaults.
          </p>
        ) : (
          <ol
            style={{
              margin: 0,
              paddingLeft: 20,
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
            }}
          >
            {weights.history.map((entry, index) => (
              <li key={entry.id}>
                <span className="mono" style={{ fontSize: 13 }}>
                  {WEIGHT_NAMES.map((name) => entry[name]).join(' · ')}
                </span>{' '}
                by {who(entry)}, {when.format(new Date(entry.changed_at))}
                {entry.restored_from !== null && (
                  <span className="muted"> (a restore)</span>
                )}
                {entry.note && <span className="muted"> · “{entry.note}”</span>}
                {index === 0 ? (
                  <span className="pill plain" style={{ marginLeft: 6 }}>
                    in use
                  </span>
                ) : (
                  <button
                    type="button"
                    className="button"
                    style={{
                      minHeight: 28,
                      padding: '2px 8px',
                      fontSize: 13,
                      marginLeft: 6,
                    }}
                    disabled={sameWeights(entry, weights.current)}
                    onClick={() => void run(() => api.restoreWeights(entry.id, null))}
                  >
                    Restore
                  </button>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  )
}
