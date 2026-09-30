/**
 * The assist panel the wireframes draw, on the three screens that draw one.
 *
 * **IT SUGGESTS AND NEVER DECIDES.** Everything it returns is prose beside
 * the organization's own button. Nothing this panel renders writes a section,
 * creates a role or registers a source - a registry is what reaches a hiker's
 * phone, and a model's reading of a GIS layer is a suggestion to check rather
 * than a change to apply. That is a property of the endpoint too: `/assist`
 * returns text and touches nothing.
 *
 * **EVERY ANSWER IS LABELLED AS ONE.** The panel carries the word
 * "suggestion" and the model's name where a reader meets them, not in a
 * footnote. An organization deciding what goes on a map is entitled to know
 * which sentences on the screen came from their own files and which came from
 * a model reading them.
 *
 * **THE FOUR FAILURES READ DIFFERENTLY, BECAUSE THEY ARE DIFFERENT.** Not
 * switched on (503) is a deployment note and says the screen works without
 * it; budget spent (429) is a fact about today and says what to do instead;
 * not opted in (409) is this organization's own decision and says where it
 * is made; a failed call (502) is a shrug and says so. Collapsing them into
 * one "something went wrong" would make the first three look like the last,
 * and the first three have answers.
 *
 * **NOTHING IS SENT THAT THE PERSON ASKING CANNOT ALREADY SEE.** The caller
 * passes the context, and on every screen that context is what is rendered
 * above the panel. That is the smallest honest answer to "what did you send
 * about us".
 *
 * **AND NOTHING IS SENT AT ALL UNTIL THE ORGANIZATION SAYS SO.** `consented`
 * is `Org.assist_opted_in` handed down, and a `false` takes the question box
 * off the screen rather than letting somebody type into a box that answers
 * 409. The server still refuses on its own - the panel not offering the box
 * is a courtesy, never the gate.
 */

import { useState } from 'react'
import { ApiError } from '../lib/api'
import { orgApi } from './orgApi'

export type AssistPanelKind = 'registry' | 'addtrail' | 'coverage'

export interface AssistPanelProps {
  readonly kind: AssistPanelKind
  readonly slug: string
  /** What the screen already shows, sent with the question. */
  readonly context: string
  readonly placeholder: string
  /** The title over the panel, matching the wireframe's own eyebrow. */
  readonly title: string
  /** The opening line, before anybody has asked anything. */
  readonly opening: string
  /** Whether the organization has turned the assistant on, from
   *  `Org.assist_opted_in`. `false` takes the question box away entirely;
   *  `undefined` means the caller did not say, and the server is still the
   *  gate - `POST /assist` answers 409 before anything is sent. */
  readonly consented?: boolean
  /** Swapped out in tests. Real callers leave it. */
  readonly ask?: (body: { panel: AssistPanelKind; question: string }) => Promise<{
    answer: string
    tokens_used: number
    tokens_left_today: number | null
  }>
}

type Standing =
  | { readonly state: 'idle' }
  | { readonly state: 'asking' }
  | { readonly state: 'answered'; readonly answer: string; readonly left: number | null }
  | { readonly state: 'off' }
  | { readonly state: 'spent'; readonly detail: string }
  | { readonly state: 'failed' }
  | { readonly state: 'needsconsent' }

/** Which of the five outcomes a response is.
 *
 *  Split out because the mapping is the part worth testing: a 503 and a 502
 *  differ by one digit and by whether there is anything the reader can do.
 *  A 409 is the fifth and reads differently again - the deployment has the
 *  assistant, and this organization has not said yes to it.
 */
export function standingFor(
  status: number,
): 'off' | 'spent' | 'failed' | 'answered' | 'needsconsent' {
  if (status === 503) return 'off'
  if (status === 429) return 'spent'
  if (status === 409) return 'needsconsent'
  // A thrown fetch carries no status, and 0 arriving here means exactly that.
  // Answering 'answered' for it and relying on the caller to undo the mistake
  // would be a trap for whoever calls this next.
  if (status === 0 || status >= 400) return 'failed'
  return 'answered'
}

export function AssistPanel({
  kind,
  slug,
  context,
  placeholder,
  title,
  opening,
  consented,
  ask,
}: AssistPanelProps) {
  const [question, setQuestion] = useState('')
  const [standing, setStanding] = useState<Standing>({ state: 'idle' })

  const send = async () => {
    const asked = question.trim()
    if (!asked) return
    setStanding({ state: 'asking' })
    try {
      if (ask) {
        const result = await ask({ panel: kind, question: `${context}\n\n${asked}` })
        setStanding({
          state: 'answered',
          answer: result.answer,
          left: result.tokens_left_today,
        })
        return
      }
      // Through `orgApi` rather than a bare fetch: that is where the API
      // base and the bearer token live, and a panel that reached past it
      // would send an unauthenticated request to an endpoint that needs one.
      const body = await orgApi.assist(slug, kind, `${context}\n\n${asked}`)
      setStanding({
        state: 'answered',
        answer: body.answer,
        left: body.tokens_left_today,
      })
    } catch (error) {
      // `apiFetch` throws on every non-2xx, so the status arrives here
      // rather than on a response object.
      const status = error instanceof ApiError ? error.status : 0
      const where = standingFor(status)
      if (where === 'spent') {
        const detail =
          error instanceof ApiError &&
          typeof error.detail === 'object' &&
          error.detail !== null
            ? String((error.detail as { detail?: unknown }).detail ?? '')
            : ''
        setStanding({ state: 'spent', detail })
      } else if (where === 'off' || where === 'needsconsent') {
        setStanding({ state: where })
      } else {
        // 'answered' cannot be reached here and is not passed through: it
        // means a 2xx, which did not throw, and it carries a field this has
        // nothing to put in.
        setStanding({ state: 'failed' })
      }
    }
  }

  // Two ways to learn the same fact about the same organization, so one
  // notice: `consented === false` arrives with the org and takes the question
  // box away before anything can be typed, and 'needsconsent' is the server
  // saying it at the 409 when the caller passed nothing.
  const notConsented = consented === false || standing.state === 'needsconsent'

  return (
    <section className="org-card org-panel">
      <div className="org-panel__head">
        <h2>{title}</h2>
        <span className="org-pill" data-tone="quiet">
          suggestions, not changes
        </span>
      </div>
      <p className="org-panel__note">{opening}</p>

      {standing.state === 'answered' ? (
        <>
          <div className="org-card">
            <span className="org-eyebrow">
              A suggestion, from Claude Sonnet reading what is above
            </span>
            <p className="org-panel__note" style={{ whiteSpace: 'pre-wrap' }}>
              {standing.answer}
            </p>
          </div>
          <p className="org-mono">
            Nothing changed. Check it against your own files before you act on it — this
            read your data, it did not verify it.
            {standing.left === null
              ? ''
              : ` ${standing.left.toLocaleString()} tokens left today.`}
          </p>
        </>
      ) : null}

      {standing.state === 'off' ? (
        <div className="org-callout" data-tone="info">
          <span>
            <strong>The assistant is not switched on here.</strong> Everything on this
            screen works without it — it reads what you have already loaded and suggests
            what to look at, which you can do yourself from the tables above.
          </span>
        </div>
      ) : null}

      {standing.state === 'spent' ? (
        <div className="org-callout" data-tone="warn">
          <span>
            <strong>Your organization has used today's assistant budget.</strong>{' '}
            {standing.detail || 'It resets 24 hours after each question.'}
          </span>
        </div>
      ) : null}

      {standing.state === 'failed' ? (
        <div className="org-callout" data-tone="warn">
          <span>
            <strong>The assistant did not answer.</strong> Nothing was changed and nothing
            was lost. Ask again if you like — we do not retry on your behalf, because a
            paid call that retries itself is a bill that grows while you are not looking.
          </span>
        </div>
      ) : null}

      {notConsented ? (
        <div className="org-callout" data-tone="info">
          <span>
            <strong>This organization has not turned the assistant on.</strong> Everything
            on this screen works without it. Until an admin turns it on in Settings,
            nothing about your trails leaves OurHike — the panel would send the section
            names, trail names, mileages and gap lists on this screen to Anthropic, and
            that is your organization's decision rather than ours.
          </span>
        </div>
      ) : null}

      {consented === false ? null : (
        <div className="org-row">
          <label className="org-field">
            <span className="org-field__label">Ask about what is on this screen</span>
            <input
              className="org-input"
              value={question}
              placeholder={placeholder}
              disabled={standing.state === 'asking'}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void send()
              }}
            />
          </label>
          <button
            type="button"
            className="org-btn org-btn--small"
            disabled={standing.state === 'asking' || !question.trim()}
            onClick={() => void send()}
          >
            {standing.state === 'asking' ? 'Reading…' : 'Ask'}
          </button>
        </div>
      )}
      {consented === false ? null : (
        <p className="org-mono">
          What goes over is what is on this screen and what you type. Your question and
          its answer are not stored — we keep a count of tokens, a date and which panel
          spent them, and nothing else.
        </p>
      )}
    </section>
  )
}
