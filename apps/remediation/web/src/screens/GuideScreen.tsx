import {
  BEFORE_YOU_GO,
  CLOSE_AND_RESTORE,
  HARDEN,
  SOURCES,
  WHO_IS_COVERED,
  type SourceKey,
  type Step,
} from '../guide'

function SourceLink({ source }: { source: SourceKey }) {
  const { title, url } = SOURCES[source]
  return (
    <a href={url} target="_blank" rel="noreferrer" style={{ fontSize: 13 }}>
      {title}
    </a>
  )
}

function Steps({ steps }: { steps: Step[] }) {
  return (
    <ol className="steps">
      {steps.map((step) => (
        <li key={step.title}>
          <b>{step.title}</b>
          {step.needsApproval && (
            <span className="approval"> · needs land-manager approval</span>
          )}
          <div>{step.detail}</div>
          {step.quote && <blockquote>“{step.quote}”</blockquote>}
          <SourceLink source={step.source} />
        </li>
      ))}
    </ol>
  )
}

/** ATC's guidance in our words, with short quotes and a link to each document (PLAN.md §7). */
export function GuideScreen() {
  return (
    <>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span className="eyebrow" style={{ color: 'var(--teal)' }}>
          Guide
        </span>
        <h1 style={{ fontSize: 36 }}>How to restore a campsite</h1>
        <p className="muted" style={{ margin: 0, maxWidth: '72ch' }}>
          A summary of ATC's published guidance, read on 2026-10-24. Each step links the
          document it comes from; read that document before the work, because it is the
          authority and this page is not. Your club and the land manager have the last
          word on any site.
        </p>
      </div>

      <div className="grid2">
        <section className="card" aria-labelledby="close">
          <h2 id="close" style={{ fontSize: 22, marginBottom: 4 }}>
            Close and restore a user-created site
          </h2>
          <p className="muted" style={{ marginTop: 0 }}>
            For a site campers made themselves that is doing damage. Most of this is one
            or two people with gloves and a free afternoon.
          </p>
          <Steps steps={CLOSE_AND_RESTORE} />
        </section>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <section className="card" aria-labelledby="harden">
            <h2 id="harden" style={{ fontSize: 22, marginBottom: 4 }}>
              Harden an official site
            </h2>
            <p className="muted" style={{ marginTop: 0 }}>
              For a shelter or club campsite that is spreading. This is a club project
              planned with ATC and the land manager, not a weekend fix.
            </p>
            <Steps steps={HARDEN} />
          </section>

          <section className="card" aria-labelledby="covered">
            <h2 id="covered" style={{ fontSize: 22, marginBottom: 8 }}>
              Who is covered
            </h2>
            <ul className="steps" style={{ paddingLeft: 20 }}>
              {WHO_IS_COVERED.map((note) => (
                <li key={note.text}>
                  {note.text}
                  <blockquote>“{note.quote}”</blockquote>
                  <SourceLink source={note.source} />
                </li>
              ))}
            </ul>
          </section>

          <section className="note" aria-labelledby="before" style={{ padding: 16 }}>
            <h2 id="before" style={{ fontSize: 22, marginBottom: 8 }}>
              Before you go
            </h2>
            <ul
              style={{
                margin: 0,
                paddingLeft: 20,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}
            >
              {BEFORE_YOU_GO.map((check) => (
                <li key={check.text}>
                  {check.text} <SourceLink source={check.source} />
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>

      <section className="card" aria-labelledby="sources">
        <h2 id="sources" className="eyebrow" style={{ marginBottom: 8 }}>
          Every document this guide draws on
        </h2>
        <ul style={{ margin: 0, paddingLeft: 20, columns: '2 320px' }}>
          {Object.entries(SOURCES).map(([key, s]) => (
            <li key={key}>
              <a href={s.url} target="_blank" rel="noreferrer">
                {s.title}
              </a>
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}
