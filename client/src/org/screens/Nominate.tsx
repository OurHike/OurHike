/**
 * A hiker offering somebody else's trails, and reviewing what we found.
 *
 * `/for-orgs/nominate/` is the door and this is the room. That page is static
 * - the site carries no sign-in at all - so the address a hiker typed arrives
 * here, where there is an account to check and a browser that can do the
 * challenge's arithmetic.
 *
 * **THE REVIEW STEP IS THE POINT OF THE SCREEN, not a confirmation on the way
 * to submitting.** The maintainer's 2026-09-17 condition on harvesting a
 * club's contacts was that the hiker keeps or abandons each one, and the
 * backend implements that literally: `POST /assist/nominate` returns the
 * reading and stores NOTHING, and only what this screen sends on the submit
 * becomes a row. A contact dropped here was never written down - there is no
 * row to leak, to export, or to delete later on that person's behalf.
 *
 * So every proposed line is on by default and droppable, the count says how
 * many will actually be written to, and the submit button names the number of
 * people it is about to email. A screen that said "3 contacts found" over a
 * list nobody could edit would satisfy the letter of that condition and none
 * of its substance.
 *
 * **NOTHING ON THIS SCREEN IS PRESENTED AS VERIFIED.** The reading is what a
 * model could see on pages we fetched, and `read_at_all` distinguishes "we
 * reached their site and found nothing" from "we could not reach their site".
 * The second is not an empty result - rendering it as one would be this screen
 * telling a hiker that a club publishes nothing.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { PageHeader } from '../components'
import { solve } from '../../lib/proofOfWork'
import { DEMO_READING, isDemoNomination } from '../demoOrg'
import {
  orgApi,
  type KeptContact,
  type KeptSource,
  type NominateReading,
  type ProposedContact,
  type ProposedSource,
} from '../orgApi'

type Stage =
  'asking' | 'working' | 'reading' | 'reviewing' | 'sending' | 'done' | 'failed'

/** A proposed line plus whether the hiker is keeping it. */
interface Keepable<T> {
  readonly item: T
  readonly keep: boolean
}

const VERDICT_WORDS: Record<ProposedSource['verdict'], string> = {
  usable: 'usable',
  closures: 'closures feed',
  found: 'found',
  not_accepted: 'we do not take these',
  unreadable: 'we could not read it',
}

export interface NominateProps {
  readonly onLeave: () => void
}

/** The address `/for-orgs/nominate/` sent, read off the URL rather than the
 *  route. It is a prefill: two `/nominate` URLs with different `?website=`
 *  are the same screen, so `lib/orgRoute.ts` does not carry it. Read once, at
 *  mount, because a hiker who edits the field should not have it reset by a
 *  re-render. */
function prefilled(): string {
  try {
    return new URL(window.location.href).searchParams.get('website') ?? ''
  } catch {
    return ''
  }
}

export function Nominate({ onLeave }: NominateProps) {
  const [website, setWebsite] = useState(prefilled)
  const [stage, setStage] = useState<Stage>('asking')
  const [attempts, setAttempts] = useState(0)
  const [problem, setProblem] = useState<string | null>(null)
  const [reading, setReading] = useState<NominateReading | null>(null)
  const [sources, setSources] = useState<Keepable<ProposedSource>[]>([])
  const [contacts, setContacts] = useState<Keepable<ProposedContact>[]>([])
  const [orgName, setOrgName] = useState('')
  const [region, setRegion] = useState('')
  const cancel = useRef<AbortController | null>(null)

  useEffect(() => () => cancel.current?.abort(), [])

  const read = useCallback(async () => {
    setProblem(null)
    setAttempts(0)
    cancel.current?.abort()
    const controller = new AbortController()
    cancel.current = controller
    try {
      // THE DEMO READS FROM A FILE AND SAYS SO, the same way the console's
      // demo org does. #600 leaves the production backend unbuilt, so without
      // this the screen a reviewer opens is an empty field and the preview's
      // camera photographs nothing that was built.
      if (isDemoNomination(website)) {
        setStage('reading')
        setReading(DEMO_READING)
        setSources(DEMO_READING.sources.map((item) => ({ item, keep: true })))
        setContacts(DEMO_READING.contacts.map((item) => ({ item, keep: true })))
        setOrgName(DEMO_READING.org_name)
        setStage('reviewing')
        return
      }
      setStage('working')
      const challenge = await orgApi.nominateChallenge()
      const solution = await solve(challenge, {
        onProgress: setAttempts,
        signal: controller.signal,
      })
      setStage('reading')
      const found = await orgApi.nominateRead({ ...challenge, website, solution })
      setReading(found)
      setSources(found.sources.map((item) => ({ item, keep: true })))
      setContacts(found.contacts.map((item) => ({ item, keep: true })))
      setOrgName(found.org_name ?? '')
      setStage('reviewing')
    } catch (error) {
      if (controller.signal.aborted) return
      setProblem(error instanceof Error ? error.message : 'Something went wrong.')
      setStage('failed')
    }
  }, [website])

  const keeping = contacts.filter((row) => row.keep)

  const submit = useCallback(async () => {
    setProblem(null)
    setStage('sending')
    try {
      if (isDemoNomination(website)) {
        setStage('done')
        return
      }
      await orgApi.nominateSubmit({
        website,
        org_name: orgName.trim(),
        region: region.trim() || null,
        sources: sources
          .filter((row) => row.keep)
          .map((row) => ({ ...row.item, proposed_by: 'reading' }) as KeptSource),
        contacts: keeping.map(
          (row) => ({ ...row.item, proposed_by: 'reading' }) as KeptContact,
        ),
      })
      setStage('done')
    } catch (error) {
      setProblem(error instanceof Error ? error.message : 'Something went wrong.')
      setStage('reviewing')
    }
  }, [website, orgName, region, sources, keeping])

  if (stage === 'done') {
    return (
      <div className="org org__body org-solo">
        <PageHeader
          eyebrow="THANK YOU"
          title="That is with them now"
          sub={`We have written to ${keeping.length} ${keeping.length === 1 ? 'person' : 'people'} at ${orgName}. Three of them have to agree before anything of theirs goes on the map.`}
        />
        <div className="org-card org-stack">
          <p>
            <strong>You are a proposer, not an admin.</strong> This gives you no standing
            at their organization and no control over their trails. If they accept, the
            organization owns it from then on — not you.
          </p>
          <p>
            You will not be told who at the club read this or what they decided
            individually. That is theirs.
          </p>
          <button className="org-btn" type="button" onClick={onLeave}>
            Back to the map
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="org org__body org-solo">
      <PageHeader
        eyebrow="ANY SIGNED-IN HIKER CAN DO THIS"
        title="Put a club on the map for them"
        sub="Give us their website. We read their published pages, you decide what is worth keeping, and three people at the club decide whether any of it goes live."
      />

      <div className="org-card org-stack">
        <label className="org-field">
          <span className="org-field__label">Their website</span>
          <input
            className="org-input"
            type="url"
            inputMode="url"
            value={website}
            placeholder="https://carolinamountainclub.org"
            onChange={(event) => setWebsite(event.target.value)}
            disabled={stage === 'working' || stage === 'reading'}
          />
        </label>

        {stage === 'working' ? (
          <p className="org-panel__note" role="status">
            Your browser is doing a few seconds of arithmetic, which is what stops this
            being used a thousand times an hour by somebody who is not you.
            {attempts > 0 ? ` ${attempts.toLocaleString()} tries so far.` : ''}
          </p>
        ) : null}
        {stage === 'reading' ? (
          <p className="org-panel__note" role="status">
            Reading their published pages…
          </p>
        ) : null}
        {problem ? (
          <p className="org-callout" role="alert">
            {problem}
          </p>
        ) : null}

        <button
          className="org-btn"
          type="button"
          onClick={read}
          disabled={!website.trim() || stage === 'working' || stage === 'reading'}
        >
          {stage === 'failed' ? 'Try again' : 'Read their site'}
        </button>
      </div>

      {reading && !reading.read_at_all ? (
        <div className="org-card org-stack">
          {/* NOT AN EMPTY RESULT. Rendering "we found nothing" here would be
              this screen telling a hiker that a club publishes nothing, which
              is a claim about somebody's organization that nobody checked. */}
          <p className="org-callout">
            We could not open their site, so we have nothing to show you about it. That is
            about us reaching them, not about what they publish.
          </p>
        </div>
      ) : null}

      {reading?.read_at_all ? (
        <div className="org-stack">
          <div className="org-card org-stack">
            <span className="org-eyebrow">
              WHAT WE READ · {reading.pages_read}{' '}
              {reading.pages_read === 1 ? 'PAGE' : 'PAGES'} OF THEIR SITE
            </span>
            {reading.summary ? <p>{reading.summary}</p> : null}
            <p className="org-panel__note">
              <strong>Read, not verified.</strong> Nobody at the club has been contacted
              yet and nothing here is a commitment — yours or theirs. Everything below
              came off a page we opened; drop anything that is wrong.
            </p>

            <label className="org-field">
              <span className="org-field__label">Their name</span>
              <input
                className="org-input"
                value={orgName}
                onChange={(event) => setOrgName(event.target.value)}
              />
            </label>
            <label className="org-field">
              <span className="org-field__label">Where they are (optional)</span>
              <input
                className="org-input"
                value={region}
                placeholder="Asheville, NC"
                onChange={(event) => setRegion(event.target.value)}
              />
            </label>
          </div>

          <div className="org-card org-stack">
            <span className="org-eyebrow">WHERE THEIR DATA LIVES</span>
            {sources.length === 0 ? (
              <p className="org-panel__note">
                We did not find anything we could re-read on the pages we opened. That
                happens — plenty of clubs publish a PDF and nothing else.
              </p>
            ) : (
              <ul className="org-stack">
                {sources.map((row, index) => (
                  <li key={row.item.url} className="org-panel">
                    <label className="org-inline">
                      <input
                        type="checkbox"
                        checked={row.keep}
                        onChange={() =>
                          setSources((all) =>
                            all.map((each, at) =>
                              at === index ? { ...each, keep: !each.keep } : each,
                            ),
                          )
                        }
                      />
                      <span>
                        <strong>{row.item.label}</strong>{' '}
                        <span className="org-pill">
                          {VERDICT_WORDS[row.item.verdict]}
                        </span>
                      </span>
                    </label>
                    <p className="org-mono">{row.item.url}</p>
                    {row.item.detail ? (
                      <p className="org-panel__note">{row.item.detail}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="org-card org-stack">
            <span className="org-eyebrow">WHO AT THE CLUB WE WOULD ASK</span>
            <p className="org-panel__note">
              {/* THE SENTENCE THAT MAKES THE REVIEW REAL. Every address here was
                  published by the club on the page named beneath it, and every
                  one is a real person's inbox. Dropping one here means it is
                  never stored - not hidden, not stored. */}
              Each of these was published on the page named beneath it. Uncheck anybody
              who is wrong, or who should not be the one asked — we only keep, and only
              ever write to, the ones you leave ticked.
            </p>
            {contacts.length === 0 ? (
              <p className="org-callout">
                We could not find an address on their site, so there is nobody for us to
                ask. A nomination needs at least one.
              </p>
            ) : (
              <ul className="org-stack">
                {contacts.map((row, index) => (
                  <li key={row.item.email} className="org-panel">
                    <label className="org-inline">
                      <input
                        type="checkbox"
                        checked={row.keep}
                        onChange={() =>
                          setContacts((all) =>
                            all.map((each, at) =>
                              at === index ? { ...each, keep: !each.keep } : each,
                            ),
                          )
                        }
                      />
                      <span>
                        <strong>
                          {row.item.name ?? row.item.role ?? 'No name given'}
                        </strong>
                        {row.item.name && row.item.role ? ` · ${row.item.role}` : null}
                      </span>
                    </label>
                    <p className="org-mono">{row.item.email}</p>
                    <p className="org-panel__note">Listed on {row.item.source_page}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="org-card org-stack">
            <p>
              <strong>Nothing publishes because you submitted it.</strong> We write to the
              people you kept and three of them have to agree — the same rule as an
              organization that signs itself up. If they say no, that is the end of it,
              and you are not told who said so.
            </p>
            {problem ? (
              <p className="org-callout" role="alert">
                {problem}
              </p>
            ) : null}
            <button
              className="org-btn"
              type="button"
              onClick={submit}
              disabled={keeping.length === 0 || !orgName.trim() || stage === 'sending'}
            >
              {stage === 'sending'
                ? 'Sending…'
                : `Write to ${keeping.length} ${keeping.length === 1 ? 'person' : 'people'} at ${orgName || 'this club'}`}
            </button>
            <button className="org-btn org-btn--ghost" type="button" onClick={onLeave}>
              Leave this and go back
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
