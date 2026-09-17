/**
 * What somebody at a nominated club sees when they open the link we mailed.
 *
 * **NO ACCOUNT, AND THAT IS THE DESIGN RATHER THAN A SHORTCUT.** Nobody at
 * the club has one, and requiring them to make one in order to answer "is
 * this yours?" would be a sign-up wall in front of a question we asked them.
 * The token in the URL is the whole of the addressing, which is why
 * `backend/app/routers/nominations.py` answers expired, withdrawn and
 * never-existed with the same 404 and the same sentence: a distinguishing
 * error is an oracle for guessing one.
 *
 * **THE REFUSAL IS AS EASY AS THE APPROVAL, and easier than reading.** A
 * screen that buries "no thank you" under a paragraph is a screen that
 * collects consent from people who gave up. So both answers are buttons, one
 * refusal ends it for everybody rather than needing three, and the stronger
 * refusal - never ask again, for any hiker, ever - is offered in plain words
 * rather than hidden behind a preference.
 *
 * **NOTHING HERE NAMES THE HIKER WHO PROPOSED THEM.** The design is explicit
 * in both directions: the club is not handed a way to contact them, and they
 * are never told who declined. `proposed_by_display` is the server's word for
 * that and this screen renders it rather than composing its own.
 *
 * `?refusing` arrives from the `List-Unsubscribe` header (RFC 8058), so a
 * mail client can offer one click without anybody reading to the bottom of
 * the message. It opens on the refusal rather than performing it: one click
 * in a mail client should not decide an organization's position silently.
 */

import { useCallback, useEffect, useState } from 'react'
import { PageHeader } from '../components'
import { orgApi, type Proposal as ProposalView } from '../orgApi'

export interface ProposalProps {
  readonly token: string
  /** True when the link came from the email's one-click unsubscribe. */
  readonly refusing?: boolean
}

const VERDICT_WORDS: Record<string, string> = {
  usable: 'we can read this',
  closures: 'a closures feed',
  found: 'found',
  not_accepted: 'we do not take these',
  unreadable: 'we could not read it',
}

export function Proposal({ token, refusing }: ProposalProps) {
  const [proposal, setProposal] = useState<ProposalView | null>(null)
  const [gone, setGone] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [sending, setSending] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    orgApi
      .proposal(token, controller.signal)
      .then(setProposal)
      .catch(() => {
        if (!controller.signal.aborted) setGone(true)
      })
    return () => controller.abort()
  }, [token])

  const decide = useCallback(
    async (approve: boolean, neverAgain = false) => {
      setProblem(null)
      setSending(true)
      try {
        setProposal(
          await orgApi.proposalDecision(token, {
            approve,
            never_ask_again: neverAgain,
          }),
        )
      } catch (error) {
        setProblem(error instanceof Error ? error.message : 'Something went wrong.')
      } finally {
        setSending(false)
      }
    },
    [token],
  )

  if (gone) {
    return (
      <div className="org-screen">
        <PageHeader
          eyebrow="THIS LINK"
          title="That link has expired, or is not one of ours"
          sub="If somebody at your organization already answered, that is the whole of it — nothing else is needed from you."
        />
      </div>
    )
  }

  if (proposal === null) {
    return <div className="org-screen">Opening…</div>
  }

  if (proposal.state === 'declined') {
    return (
      <div className="org-screen">
        <PageHeader
          eyebrow="ANSWERED"
          title="Nothing of yours is going anywhere"
          sub="Somebody at your organization declined this. No trail data of yours has been published, and the hiker who proposed it is not told who declined."
        />
      </div>
    )
  }

  if (proposal.state === 'accepted') {
    return (
      <div className="org-screen">
        <PageHeader
          eyebrow="ACCEPTED"
          title={`${proposal.org_name}'s trails are yours to run`}
          sub="Three people here agreed. From now on the organization owns this — not the hiker who proposed it."
        />
      </div>
    )
  }

  return (
    <div className="org-screen">
      <PageHeader
        eyebrow="FOR THE CLUBS WHO CUT THE TREAD"
        title="A hiker wants to put your trails on the map."
        sub={`${proposal.proposed_by_display} has proposed adding ${proposal.org_name}'s trails to OurHike. They are not affiliated with your organization, and nothing has been published.`}
      />

      {refusing ? (
        <div className="org-callout">
          {/* ARRIVED FROM THE EMAIL'S ONE CLICK. It opens here rather than
              acting: a single click in a mail client should not decide an
              organization's position without anybody reading what it was
              about. */}
          You followed the “no thank you” link. Nothing has happened yet — the button is
          below, and it is final.
        </div>
      ) : null}

      <div className="org-card org-stack">
        <span className="org-eyebrow">WHAT YOUR ORGANIZATION WOULD GET, AT NO COST</span>
        <ul className="org-stack">
          <li>
            <strong>Beautiful maps, free to every hiker.</strong> Your sections drawn from
            your own data, working with no bars and no data plan.
          </li>
          <li>
            <strong>Trail problems reach whoever covers that mile.</strong> A blowdown
            reported at noon, not a generic inbox.
          </li>
          <li>
            <strong>Every hiker learns about volunteering.</strong> Your workdays appear
            where hikers already look.
          </li>
          <li>
            <strong>Members and donations reach you.</strong> We link your own membership
            and giving pages. No money passes through us.
          </li>
        </ul>
      </div>

      <div className="org-card org-stack">
        <span className="org-eyebrow">WHAT WE FOUND ON YOUR OWN PAGES</span>
        {proposal.sources.length === 0 ? (
          <p className="org-help">
            Nothing we could re-read. Whoever proposed this described your trails in their
            own words.
          </p>
        ) : (
          <ul className="org-stack">
            {proposal.sources.map((source) => (
              <li key={source.url} className="org-panel">
                <strong>{source.label}</strong>{' '}
                <span className="org-pill">
                  {VERDICT_WORDS[source.verdict] ?? source.verdict}
                </span>
                <p className="org-mono">{source.url}</p>
                {source.detail ? <p className="org-help">{source.detail}</p> : null}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="org-card org-stack">
        <span className="org-eyebrow">
          WHO WE ASKED · {proposal.approvals_so_far} OF {proposal.approvals_required} HAVE
          AGREED
        </span>
        <p className="org-help">
          These addresses are published on your own site. If the wrong people are listed,
          declining is the right answer — we will not go looking for others.
        </p>
        <ul className="org-stack">
          {proposal.contacts.map((contact) => (
            <li key={contact.email} className="org-panel">
              <strong>{contact.name ?? contact.role ?? 'No name given'}</strong>
              <p className="org-mono">{contact.email}</p>
              <p className="org-help">
                From {contact.source_page}
                {contact.responded ? ' · has answered' : ''}
              </p>
            </li>
          ))}
        </ul>
      </div>

      <div className="org-card org-stack">
        <p>
          <strong>
            Nothing goes live unless {proposal.approvals_required} of you approve it.
          </strong>{' '}
          Your data stays yours — OurHike is open source, so you can fork it and walk away
          at any point.
        </p>
        {problem ? (
          <p className="org-callout" role="alert">
            {problem}
          </p>
        ) : null}
        <div className="org-inline">
          <button
            className="btn"
            type="button"
            disabled={sending}
            onClick={() => decide(true)}
          >
            This is ours — go ahead
          </button>
          <button
            className="btn btn--ghost"
            type="button"
            disabled={sending}
            onClick={() => decide(false)}
          >
            No thank you
          </button>
        </div>
        <p className="org-help">
          Would rather nobody proposed your data at all?{' '}
          <button
            className="org-link"
            type="button"
            disabled={sending}
            onClick={() => decide(false, true)}
          >
            Tell us never to ask again
          </button>{' '}
          — we will honour that for good, including for any other hiker who tries later,
          and whoever proposed this is not told who declined.
        </p>
      </div>
    </div>
  )
}
