/**
 * The four embeds: what to paste, what it will not do, and the key exchange.
 *
 * **THREE ARE PUBLIC AND THE FOURTH IS NOT, AND THE SCREEN SAYS WHICH BEFORE
 * THE SNIPPET.** The public three read a published registry and hold no
 * credential, so they are one line of HTML and a script tag. The console is a
 * key, a call from an organization's own server, and a token - and an
 * organization discovering that after pasting it is an organization who put a
 * secret in a page.
 *
 * **THE SECRET IS SHOWN ONCE AND NEVER AGAIN.** `POST /clubs/{slug}/
 * console-keys` returns it on the creating response only; a later list gives
 * the public half and nothing else. This screen cannot re-show it because
 * there is nothing stored to re-show, which is what makes "we cannot read
 * your key" a fact about the system rather than a policy.
 *
 * **THE SNIPPET NEVER CONTAINS THE SECRET.** What an organization pastes has
 * their public key in it, which is fine and is meant to be in page source.
 * The secret goes in their server's configuration, and the screen shows the
 * server-side call separately so the two cannot be confused - the embed file
 * itself refuses a `data-secret` attribute for the same reason.
 *
 * **WHAT IT WILL NOT DO IS PART OF THE OFFER.** No cookies, no tracking, no
 * branding they cannot remove, inherits their fonts and colours, and their
 * page still renders when we are down. Those four sentences are checked
 * against the file that has to keep them, in
 * `client/src/test/orgEmbeds.test.ts`, so they are a contract rather than a
 * claim.
 */

import { useState } from 'react'
import { PageHeader, HikeFinder, WorkdaysWidget, CoverageBadge } from '../components'
import type { FinderHike } from '../components'
import type { ConsoleKey, Workday } from '../orgApi'
import type { UnitSystem } from '../../lib/units'

export type EmbedKind = 'hikes' | 'workdays' | 'coverage' | 'console'

export interface EmbedsProps {
  readonly orgName: string
  readonly slug: string
  /** Where the script is served from, so the snippet is copy-pasteable. */
  readonly scriptOrigin: string
  readonly hikes: readonly FinderHike[]
  readonly workdays: readonly Workday[]
  readonly gaps: number
  readonly sectionsTotal: number
  readonly keys: readonly ConsoleKey[]
  /** The secret, on the one render that created it. Never stored. */
  readonly freshSecret: string | null
  /** False when the deployment has not turned the console embed on. */
  readonly consoleEnabled: boolean
  readonly canEdit: boolean
  readonly onCreateKey: (label: string, origins: readonly string[]) => void
  readonly onRevokeKey: (key: ConsoleKey) => void
  /** The hiker's own choice, from Settings. Never assumed - #619. */
  readonly units: UnitSystem
}

const TABS: readonly { key: EmbedKind; label: string }[] = [
  { key: 'hikes', label: 'Find a hike' },
  { key: 'workdays', label: 'Workdays' },
  { key: 'coverage', label: 'Coverage badge' },
  { key: 'console', label: 'Management console' },
]

/**
 * The paste, for one embed.
 *
 * Built from the org's own slug rather than shown as a template with a
 * placeholder to fill in, because a placeholder is a step somebody gets
 * wrong silently - the widget renders nothing and they have no way to tell
 * that from an outage.
 */
export function snippetFor(kind: EmbedKind, slug: string, scriptOrigin: string): string {
  const src = `${scriptOrigin.replace(/\/$/, '')}/embed/v1/ourhike.js`
  const tag = `<script src="${src}" async></script>`
  switch (kind) {
    case 'hikes':
      return `<div id="ourhike-hikes" data-org="${slug}" data-filters="region,length" data-rows="25"></div>\n${tag}`
    case 'workdays':
      return `<div id="ourhike-workdays" data-org="${slug}" data-window="60"></div>\n${tag}`
    case 'coverage':
      return `<div id="ourhike-coverage" data-org="${slug}"></div>\n${tag}`
    default:
      return `<div id="ourhike-console" data-org="${slug}" data-token="<the token your server just minted>"></div>\n${tag}`
  }
}

const WHAT_IT_DOES: Record<EmbedKind, string> = {
  hikes:
    'Your featured hikes, filterable, reading the registry you already signed off. It updates when your registry does — you never paste a list again.',
  workdays:
    'Your upcoming work. A workday mirrored from your own calendar sends its signup to your form and says so; one made in OurHike uses ours. A visitor cannot tell which is which, and should not have to.',
  coverage:
    'The small one, for a sidebar. It counts sections with nobody assigned — a recruiting line, not an alarm. No visitor is told a section is unmaintained.',
  console:
    'The management console, inside your own members area. Same paste, plus one call from your server to vouch for whoever is signed in over there.',
}

export function Embeds({
  orgName,
  slug,
  scriptOrigin,
  hikes,
  workdays,
  gaps,
  sectionsTotal,
  keys,
  freshSecret,
  consoleEnabled,
  canEdit,
  onCreateKey,
  onRevokeKey,
  units,
}: EmbedsProps) {
  const [tab, setTab] = useState<EmbedKind>('hikes')
  const [label, setLabel] = useState('')
  const [origins, setOrigins] = useState('')
  const [copied, setCopied] = useState(false)

  const snippet = snippetFor(tab, slug, scriptOrigin)
  const live = keys.filter((key) => key.revoked_at === null)

  return (
    <>
      <PageHeader
        eyebrow="Your own website · 3 public · 1 private"
        title="Put this on your own site"
        sub={
          <>
            The first three are one line of HTML and a script tag, public, no account
            needed to view. The fourth is the private console — same paste, plus one call
            from your server to vouch for whoever is signed in. All four read your
            published registry, so they stay current without you touching them, and they
            carry your own membership and donation links, not ours.
          </>
        }
        glyph={
          <>
            <path d="M9 8 5 12l4 4M15 8l4 4-4 4" />
          </>
        }
      />

      <div className="org-chips">
        {TABS.map((entry) => (
          <button
            key={entry.key}
            type="button"
            className="org-chip"
            aria-pressed={tab === entry.key}
            onClick={() => {
              setTab(entry.key)
              setCopied(false)
            }}
          >
            {entry.label}
          </button>
        ))}
      </div>

      <section className="org-card org-panel">
        <div className="org-panel__head">
          <h2>Paste this where it should appear</h2>
          <button
            type="button"
            className="org-link"
            onClick={() => {
              void navigator.clipboard?.writeText(snippet)
              setCopied(true)
            }}
          >
            {copied ? 'copied' : 'copy'}
          </button>
        </div>
        <pre className="org-code">{snippet}</pre>
        <p className="org-panel__note">{WHAT_IT_DOES[tab]}</p>
        <span className="org-eyebrow">What it will not do</span>
        <p className="org-panel__note">
          No cookies, no tracking, no OurHike branding you cannot remove, and it inherits
          your fonts and colours. If our servers are down your page still renders — the
          embed just does not appear.
        </p>
        <p className="org-mono">
          Add <code>data-credit="off"</code> to drop the “drawn by OurHike” line. It is on
          by default because it is how a visitor works out who to tell when a mile is
          wrong, not because it is ours to insist on.
        </p>
      </section>

      {tab === 'console' ? (
        <>
          <div className="org-callout" data-tone="warn">
            <span>
              <strong>The secret never goes in the page.</strong> Your public key is in
              the paste and is meant to be — anybody can read it and it opens nothing.
              Your server holds the secret, calls <code>POST /console/session</code> with
              it and the signed-in person's email, and puts the token it gets back into{' '}
              <code>data-token</code>. The embed refuses a secret in an attribute rather
              than using one.
            </span>
          </div>

          {!consoleEnabled ? (
            <div className="org-callout" data-tone="info">
              <span>
                <strong>This one is built and not switched on.</strong> The endpoints
                answer 503 until a deployment enables the console embed. The three public
                embeds above work regardless — they read a published registry and hold no
                credential.
              </span>
            </div>
          ) : null}

          <section className="org-panel">
            <div className="org-panel__head">
              <h2>Your console keys</h2>
              <span className="org-panel__count">
                {live.length} live · {keys.length - live.length} revoked
              </span>
            </div>
            <p className="org-panel__note">
              A key is scoped to the origins you name here. A token minted with it is
              worthless on any other site, checked when it is minted and again every time
              it is used.
            </p>

            {freshSecret ? (
              <div className="org-callout" data-tone="stop">
                <span>
                  <strong>Copy this now. It is not shown again.</strong>
                  <br />
                  <code>{freshSecret}</code>
                  <br />
                  We do not store it — only a hash — so we could not show it to you a
                  second time even if you asked. Lost means make a new key and revoke this
                  one.
                </span>
              </div>
            ) : null}

            {keys.length === 0 ? (
              <div className="org-empty">
                <h3>No keys yet</h3>
                <p>
                  You need one only for the console embed. The three public ones above
                  need no key and no account.
                </p>
              </div>
            ) : (
              <div className="org-card org-card--flush">
                <table className="org-table">
                  <thead>
                    <tr>
                      <th scope="col">Label</th>
                      <th scope="col">Public key</th>
                      <th scope="col">Origins</th>
                      <th scope="col">Last used</th>
                      <th scope="col" />
                    </tr>
                  </thead>
                  <tbody>
                    {keys.map((key) => (
                      <tr key={key.id}>
                        <td className="org-table__name">{key.label ?? 'unlabelled'}</td>
                        <td className="org-mono">{key.public_key}</td>
                        <td className="org-mono">
                          {key.allowed_origins.join(' ') || 'none'}
                        </td>
                        <td className="org-mono">
                          {key.last_used_at ? key.last_used_at.slice(0, 10) : 'never'}
                        </td>
                        <td>
                          {key.revoked_at ? (
                            <span className="org-pill" data-tone="quiet">
                              revoked
                            </span>
                          ) : canEdit ? (
                            <button
                              type="button"
                              className="org-link"
                              onClick={() => onRevokeKey(key)}
                            >
                              revoke
                            </button>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {canEdit ? (
              <div className="org-card org-stack">
                <div className="org-row">
                  <label className="org-field">
                    <span className="org-field__label">What this key is for</span>
                    <input
                      className="org-input"
                      value={label}
                      placeholder="Members area"
                      onChange={(event) => setLabel(event.target.value)}
                    />
                  </label>
                  <label className="org-field">
                    <span className="org-field__label">
                      Which sites may use it, one per line — exact origins, no wildcards
                    </span>
                    <textarea
                      className="org-textarea"
                      value={origins}
                      placeholder={`https://members.${orgName.toLowerCase().replace(/\s+/g, '')}.org`}
                      onChange={(event) => setOrigins(event.target.value)}
                    />
                  </label>
                </div>
                <div className="org-inline">
                  <button
                    type="button"
                    className="org-btn org-btn--small"
                    disabled={!origins.trim()}
                    onClick={() =>
                      onCreateKey(
                        label.trim(),
                        origins
                          .split('\n')
                          .map((line) => line.trim())
                          .filter(Boolean),
                      )
                    }
                  >
                    Make a key
                  </button>
                  <span className="org-mono">
                    A wildcard is refused rather than narrowed. “Every subdomain we might
                    ever have” is not a boundary.
                  </span>
                </div>
              </div>
            ) : null}
          </section>
        </>
      ) : (
        <section className="org-panel">
          <div className="org-panel__head">
            <h2>Live preview</h2>
            <span className="org-panel__count">this is what visitors see</span>
          </div>
          {tab === 'hikes' ? (
            <>
              <HikeFinder hikes={hikes} orgName={orgName} units={units} />
              <div className="org-callout" data-tone="warn">
                <span>
                  <strong>The preview offers one filter the embed does not.</strong> This
                  is drawn with the app's own finder, which has a difficulty for every
                  hike. The embed reads your published registry, and a registry section
                  carries no difficulty — so its paste asks for <code>region,length</code>{' '}
                  and it draws those two. Saying so here is cheaper than an organization
                  discovering it on their own homepage.
                </span>
              </div>
            </>
          ) : tab === 'workdays' ? (
            <>
              <WorkdaysWidget
                workdays={workdays}
                emptyNote="Nothing on the calendar in the window. A visitor sees this same sentence rather than an empty box."
              />
              <p className="org-mono">
                A mirrored workday says “Sign up on our site” and the button goes to your
                form, not ours. One made in OurHike uses our signup.
              </p>
            </>
          ) : (
            <div style={{ maxWidth: 340 }}>
              <CoverageBadge gaps={gaps} total={sectionsTotal} />
            </div>
          )}
          <p className="org-mono">
            Published by {orgName} · drawn by OurHike — the one line{' '}
            <code>data-credit="off"</code> removes.
          </p>
        </section>
      )}
    </>
  )
}
