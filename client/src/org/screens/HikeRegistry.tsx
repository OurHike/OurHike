/**
 * Stage 2: an organization's own GIS, read with them.
 *
 * **WE READ THEIR FILES AND ASK ONLY ABOUT WHAT WE CANNOT RESOLVE.** That is
 * the promise the whole screen is built to keep: an organization that has to
 * answer three hundred questions to publish three hundred sections will stop
 * at forty. So the summary leads with how many were clean, and the button is
 * "review the exceptions" rather than "review everything".
 *
 * **SECTION NAMES COME FROM THEIR OWN ATTRIBUTE.** `SECT_NAME`, or whatever
 * their column is called. A registry that renamed an organization's sections
 * to something tidier would be a registry their own crew leads could not
 * read, and the point of asking them for the data was that they know it.
 *
 * **ENDS ARE ANCHORED TO MILE MARKERS AND POIs, NEVER FREE TEXT.**
 * SEGMENTS.md's rule, and the thing that lets a report written years from now
 * find the right maintainer: "from the big oak to the second stream crossing"
 * cannot be resolved by a lookup, so an anchor that is free text is an anchor
 * that stops working the first time a section changes hands.
 *
 * **A FLAT FILE IS REFUSED, AND THE REFUSAL SAYS WHY.** A PDF cannot be
 * re-read, so accepting one would be accepting a snapshot while implying a
 * feed - and the nightly diff would silently never happen.
 */

import { AssistPanel } from '../AssistPanel'
import { useState } from 'react'
import { PageHeader, RegistryTable, SectionMap } from '../components'
import type { OrgPark, OrgSection } from '../orgApi'

export interface RegistrySource {
  readonly id: string
  readonly label: string
  readonly url: string
  readonly summary: string
  readonly cadence: string
  readonly state: 'in sync' | 'changes waiting' | 'manual'
  readonly changes?: number
}

export interface HikeRegistryProps {
  readonly orgName: string
  readonly registry: readonly OrgPark[]
  readonly sources: readonly RegistrySource[]
  readonly featuredHikes: number
  /** Lines we could not resolve without the org: no name, a gap between ends,
   *  or two that look like duplicates. */
  readonly needsAnEye: number
  readonly onAddSource: (url: string, kind: string) => Promise<string>
  readonly onSendForSignoff: () => void
  readonly slug: string
}

/** What we can read again tomorrow, which is the whole criterion. */
const SOURCE_KINDS = [
  { value: 'arcgis', label: 'ArcGIS REST / FeatureServer' },
  { value: 'wfs', label: 'WMS / WFS endpoint' },
  { value: 'geojson', label: 'GeoJSON at a URL' },
  { value: 'shapefile_zip', label: 'A zipped shapefile set' },
]

export function HikeRegistry({
  orgName,
  registry,
  sources,
  featuredHikes,
  needsAnEye,
  onAddSource,
  onSendForSignoff,
  slug,
}: HikeRegistryProps) {
  const [url, setUrl] = useState('')
  const [kind, setKind] = useState(SOURCE_KINDS[0].value)
  const [answer, setAnswer] = useState<string | null>(null)
  const [refusal, setRefusal] = useState<string | null>(null)
  const [selected, setSelected] = useState<OrgSection | null>(null)

  const sections = registry.flatMap((park) =>
    park.trails.flatMap((trail) => trail.sections),
  )
  const clean = Math.max(0, sections.length - needsAnEye)

  const submit = async () => {
    setAnswer(null)
    setRefusal(null)
    try {
      setAnswer(await onAddSource(url.trim(), kind))
      setUrl('')
    } catch (error) {
      setRefusal(
        error instanceof Error
          ? error.message
          : 'We could not register that source. Check the URL and try again.',
      )
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Stage 2 of 3 · hike registry"
        title="Let's turn your GIS into sections hikers can read"
        sub={
          <>
            We read your files, keep your own section names, and only ask about the lines
            we cannot resolve on our own.
          </>
        }
        glyph={
          <>
            <path d="M3 6.5 9 4l6 2.5L21 4v13.5L15 20l-6-2.5L3 20z" />
            <path d="M9 4v13.5M15 6.5V20" />
          </>
        }
      />

      <AssistPanel
        kind="registry"
        slug={slug}
        title="Registry assistant"
        opening="Point it at your GIS however it exists — a feature server, a WMS endpoint, a bucket, or your public downloads page. It reports what it can see and says what it cannot; reading a layer is not the same as publishing one, and nothing here publishes."
        placeholder="It's all on gis.example.org/arcgis/rest/… — names are in SECT_NAME"
        context={`${sections.length} sections read so far, ${clean} clean, ${needsAnEye} needing a person. Sources connected: ${sources.length}.`}
      />

      <section className="org-grid org-grid--two">
        <div className="org-card org-panel">
          <span className="org-eyebrow">What we read</span>
          <div className="org-grid org-grid--three">
            <div className="org-tile">
              <span className="org-tile__label">Sections</span>
              <span className="org-tile__value">{sections.length}</span>
            </div>
            <div className="org-tile">
              <span className="org-tile__label">Clean</span>
              <span className="org-tile__value">{clean}</span>
            </div>
            <div className="org-tile">
              <span className="org-tile__label">Need your eye</span>
              <span className="org-tile__value">{needsAnEye}</span>
            </div>
            <div className="org-tile">
              <span className="org-tile__label">Featured hikes</span>
              <span className="org-tile__value">{featuredHikes}</span>
            </div>
          </div>
          <p className="org-panel__note">
            Section names come from your own attribute. Ends are anchored to mile markers
            and trailhead points, so a report written years from now still finds the right
            maintainer.
          </p>
          {needsAnEye > 0 ? (
            <div className="org-callout" data-tone="warn">
              <span>
                <strong>{needsAnEye} lines need you rather than us.</strong> A missing
                name, a gap between ends, or two that look like the same trail twice. The
                other {clean} came straight out of your own files.
              </span>
            </div>
          ) : null}
        </div>

        <div className="org-card org-panel">
          <div className="org-panel__head">
            <h2>Where it came from</h2>
            <span className="org-panel__count">
              {sources.length} {sources.length === 1 ? 'source' : 'sources'}
            </span>
          </div>
          <p className="org-panel__note">
            Most organizations do not keep everything in one place. Point us at as many as
            you like — each is read on its own schedule, and they merge into one registry.
          </p>
          <div className="org-stack">
            {sources.map((source) => (
              <div className="org-card" key={source.id}>
                <div className="org-inline">
                  <span className="org-table__name">{source.label}</span>
                  <span
                    className="org-pill"
                    data-tone={
                      source.state === 'in sync'
                        ? 'done'
                        : source.state === 'manual'
                          ? 'quiet'
                          : 'waiting'
                    }
                    style={{ marginLeft: 'auto' }}
                  >
                    {source.state === 'changes waiting'
                      ? `${source.changes ?? 0} changes waiting`
                      : source.state === 'manual'
                        ? 'no server — re-upload to change'
                        : 'in sync'}
                  </span>
                </div>
                <p className="org-mono">{source.url}</p>
                <p className="org-mono">
                  {source.summary} · {source.cadence}
                </p>
              </div>
            ))}
          </div>

          <div className="org-row">
            <label className="org-field">
              <span className="org-field__label">
                Another server, endpoint or data portal
              </span>
              <input
                className="org-input"
                type="url"
                inputMode="url"
                placeholder="https://gis.example.org/arcgis/rest/services/Trails/FeatureServer/0"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
              />
            </label>
            <label className="org-field" style={{ flex: '0 1 220px' }}>
              <span className="org-field__label">What kind</span>
              <select
                className="org-select"
                value={kind}
                onChange={(event) => setKind(event.target.value)}
              >
                {SOURCE_KINDS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="org-btn org-btn--small"
              disabled={!url.trim()}
              onClick={submit}
            >
              Add source
            </button>
          </div>
          <p className="org-mono">
            We do not accept PDFs, screenshots or spreadsheets — only something we can
            re-read. A snapshot that looks like a feed is worse than no source at all.
          </p>
          {answer ? (
            <div className="org-callout" data-tone="good">
              <span>{answer}</span>
            </div>
          ) : null}
          {refusal ? (
            <div className="org-callout" data-tone="stop">
              <span>{refusal}</span>
            </div>
          ) : null}
        </div>
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>What we have built so far</h2>
          <span className="org-panel__count">click a row to see only that section</span>
        </div>
        <p className="org-panel__note">
          Park or trail system, then trail, then section. This is the same table your
          admins will sign off.
        </p>
        <div className="org-grid org-grid--two">
          <RegistryTable
            parks={registry}
            selectedSectionId={selected?.id ?? null}
            onSelect={setSelected}
          />
          <SectionMap
            sections={sections}
            highlightId={selected?.id ?? null}
            caption={
              selected
                ? `${selected.name} · ${selected.start_anchor ?? '?'} → ${selected.end_anchor ?? '?'}`
                : `All ${sections.length} sections · schematic, drawn from the geometry you gave us`
            }
          />
        </div>
      </section>

      <div className="org-inline">
        <button type="button" className="org-btn" onClick={onSendForSignoff}>
          Send to admins for sign-off
        </button>
        <span className="org-mono">
          Your registry is committed to OurHike's public repository as a pull request —
          your admins review it there, in the open.
        </span>
      </div>

      <div className="org-callout" data-tone="info">
        <span>
          If two sources describe the same trail we flag the overlap rather than
          publishing it twice. A changed source produces a diff for your admins —{' '}
          <strong>the published map never moves on its own.</strong>
        </span>
      </div>

      <p className="org-mono">Registry for {orgName}.</p>
    </>
  )
}
