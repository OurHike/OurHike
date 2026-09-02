import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { StatusStrip } from './StatusStrip'

// WIREFRAMES.md, map screen §1: time, GPS/offline state, sync age.
//
// This strip is where the map admits what it doesn't know. WIREFRAMES.md `7b`
// (no GPS fix) and its "loading/empty/error states are first-class" rule both
// land here: going offline or losing the fix is a normal condition on trail,
// not an error, and the strip has to say so plainly rather than silently
// showing a stale position as if it were live.

const AT_NOON = new Date('2026-07-29T12:00:00')

const PROPS = {
  time: AT_NOON,
  online: true,
  hasGpsFix: true,
  lastSyncedAt: new Date('2026-07-29T09:00:00'),
}

afterEach(() => {
  cleanup()
})

describe('StatusStrip', () => {
  it('shows the current time', () => {
    render(<StatusStrip {...PROPS} />)

    expect(screen.getByText(/12:00/)).toBeInTheDocument()
  })

  it('says nothing about connectivity while online - no badge for the normal case', () => {
    render(<StatusStrip {...PROPS} />)

    expect(screen.queryByText(/offline/i)).not.toBeInTheDocument()
  })

  it('states plainly that it is offline when there is no signal', () => {
    render(<StatusStrip {...PROPS} online={false} />)

    expect(screen.getByText(/offline/i)).toBeInTheDocument()
  })

  it('says the GPS fix is lost rather than showing a stale position as if it were live', () => {
    render(<StatusStrip {...PROPS} hasGpsFix={false} />)

    expect(screen.getByText(/no gps/i)).toBeInTheDocument()
  })

  it('says the view is past the edge of the download, in the words of coverage (#557)', () => {
    render(<StatusStrip {...PROPS} outsideDownload />)

    const flag = screen.getByText(/outside what you downloaded/i)
    expect(flag).toBeInTheDocument()
    // Never damage. A hiker past the edge of the stretch they took is
    // looking at paper because the ground was never taken, and the wording
    // #352 had to walk back would send them to delete a download that is
    // fine.
    expect(flag.textContent).not.toMatch(/damaged|corrupt|incomplete|not drawing/i)
  })

  it('says nothing about the edge on a phone that has not crossed one', () => {
    render(<StatusStrip {...PROPS} />)

    expect(screen.queryByText(/outside what you downloaded/i)).not.toBeInTheDocument()
  })

  it('reports how long ago the data last synced', () => {
    render(<StatusStrip {...PROPS} />)

    expect(screen.getByText(/3h ago/i)).toBeInTheDocument()
  })

  it('reports sync age in days once it is past a day old', () => {
    render(
      <StatusStrip {...PROPS} lastSyncedAt={new Date('2026-07-26T12:00:00')} />, // 3 days
    )

    expect(screen.getByText(/3d ago/i)).toBeInTheDocument()
  })

  it('says "just now" for a sync within the last minute', () => {
    render(<StatusStrip {...PROPS} lastSyncedAt={new Date('2026-07-29T11:59:30')} />)

    expect(screen.getByText(/just now/i)).toBeInTheDocument()
  })

  it('says the data has never synced rather than leaving the age blank', () => {
    render(<StatusStrip {...PROPS} lastSyncedAt={null} />)

    expect(screen.getByText(/never synced/i)).toBeInTheDocument()
  })

  it('announces offline and lost-fix changes politely to assistive tech', () => {
    render(<StatusStrip {...PROPS} online={false} hasGpsFix={false} />)

    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('says the live map never loaded, which "Offline" cannot say', () => {
    // The gap this closes: navigator.onLine is optimistic, so a captive
    // portal, a filtered network or an outage at the tile host all read as a
    // working connection. For a hiker who has downloaded nothing there is no
    // archive underneath either, so the screen is blank paper - and until
    // this flag existed, nothing anywhere said why.
    render(<StatusStrip {...PROPS} backgroundProblem="live-unreachable" />)

    expect(screen.getByText(/no live map/i)).toBeInTheDocument()
  })

  it('says a download is on the phone and not drawing', () => {
    // The sentence #314 exists for. An archive that is present and unreadable
    // kept every indicator green - "downloaded" on the card, an honoured
    // offline background in the shell - while the map drew nothing, and the
    // hiker had no way to connect the blank paper to the download.
    render(<StatusStrip {...PROPS} backgroundProblem="download-not-drawing" />)

    expect(screen.getByText(/downloaded map not drawing/i)).toBeInTheDocument()
  })

  it('says offline that there is no download to draw, beside "Offline"', () => {
    // The other half of #314, and the reason this is no longer suppressed
    // while offline. "Offline" says the phone has no connection; it does not
    // say the download is the missing half - which is what someone who
    // deleted the hiking sheet an hour ago actually needs told.
    render(<StatusStrip {...PROPS} online={false} backgroundProblem="nothing-to-draw" />)

    expect(screen.getByText(/no downloaded map/i)).toBeInTheDocument()
    expect(screen.getByText(/offline/i)).toBeInTheDocument()
  })

  it('says when the trail line itself is not on the map', () => {
    // Every other flag here is about the sheet UNDER the trail, and a hiker
    // who loses the sheet still has the line they are walking. This is the
    // one that says the line is gone - the state that read, to the person who
    // reported it, as "the centerline isn't showing".
    render(<StatusStrip {...PROPS} trailLinesMissing />)

    expect(screen.getByText(/no trail line/i)).toBeInTheDocument()
  })

  it('says the trail line is missing even while the background is failing too', () => {
    // Unlike the two readings of one blank screen below, these are two
    // different things absent. Told only "No live map", a hiker would
    // reasonably conclude the trail is under it somewhere.
    render(
      <StatusStrip {...PROPS} backgroundProblem="live-unreachable" trailLinesMissing />,
    )

    expect(screen.getByText(/no live map/i)).toBeInTheDocument()
    expect(screen.getByText(/no trail line/i)).toBeInTheDocument()
  })

  it('stays quiet about the trail line when there is one', () => {
    render(<StatusStrip {...PROPS} backgroundProblem="live-unreachable" />)

    expect(screen.queryByText(/no trail line/i)).not.toBeInTheDocument()
  })

  it('drops "nothing downloaded yet" when the background has a real problem', () => {
    // Two flags for one blank screen, and the reassuring one reads first:
    // the override describes what the app is TRYING to draw, the problem what
    // is actually arriving.
    render(
      <StatusStrip
        {...PROPS}
        online={false}
        backgroundOverride="nothing-downloaded"
        backgroundProblem="nothing-to-draw"
      />,
    )

    expect(screen.queryByText(/nothing downloaded yet/i)).not.toBeInTheDocument()
    expect(screen.getByText(/no downloaded map/i)).toBeInTheDocument()
  })

  it('says when Data Saver is the reason the live map is missing', () => {
    // lib/dataSaver.ts's rule is that the app may override a preference and
    // may not do it silently. Settings said so; the map screen did not, and
    // the map screen is where the override is actually visible - as nothing
    // at all, on a phone with no download.
    render(<StatusStrip {...PROPS} backgroundOverride="data-saver" />)

    expect(screen.getByText(/data saver/i)).toBeInTheDocument()
  })

  it('says the live map is standing in for a download that is not there yet', () => {
    // The opposite reason, and it must not borrow the Data Saver words: here
    // the app is fetching tiles rather than withholding them.
    render(<StatusStrip {...PROPS} backgroundOverride="nothing-downloaded" />)

    expect(screen.getByText(/nothing downloaded yet/i)).toBeInTheDocument()
    expect(screen.queryByText(/data saver/i)).not.toBeInTheDocument()
  })

  it('stays quiet about the background when nothing is wrong with it', () => {
    render(<StatusStrip {...PROPS} />)

    expect(screen.queryByText(/no live map/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/data saver/i)).not.toBeInTheDocument()
  })

  it('says when the view is zoomed out past what the download covers', () => {
    // #216. Without this the app draws paper and offers no account of itself,
    // which is exactly how a complete 314 MB download came to be reported as
    // "no data downloaded".
    render(<StatusStrip {...PROPS} belowArchiveZoom />)

    expect(screen.getByText(/zoomed out past your download/i)).toBeInTheDocument()
  })

  it('does not call that an override, because nothing was overridden', () => {
    // The chosen background IS what is drawn; it simply has no tiles at this
    // scale. Borrowing either override's wording would be the quiet mismatch
    // lib/dataSaver.ts exists to prevent, one condition further along.
    render(<StatusStrip {...PROPS} belowArchiveZoom />)

    expect(screen.queryByText(/data saver/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/nothing downloaded yet/i)).not.toBeInTheDocument()
  })

  it('stays quiet while the download does cover the view', () => {
    render(<StatusStrip {...PROPS} />)

    expect(screen.queryByText(/zoomed out past/i)).not.toBeInTheDocument()
  })
})

describe('how old the closures are', () => {
  it('says nothing when the closures came from a live read', () => {
    // A caveat on data that has none teaches people to ignore caveats, which
    // costs more than it buys the one time the caveat matters.
    render(<StatusStrip {...PROPS} conditionsAge={null} />)

    expect(screen.queryByText(/Conditions as of/)).toBeNull()
    expect(screen.queryByText(/conditions unavailable/i)).toBeNull()
  })

  it('says how old a published baseline is', () => {
    render(<StatusStrip {...PROPS} conditionsAge="Conditions as of 6h ago" />)

    expect(screen.getByText('Conditions as of 6h ago')).toBeTruthy()
  })

  it('says conditions are unavailable rather than showing a reassuring blank', () => {
    // The #249 fix as a hiker meets it. Before this, neither source being
    // reachable rendered exactly like a stretch of trail with nothing closed
    // on it - the strip is where those two stop looking identical.
    render(<StatusStrip {...PROPS} conditionsAge="Trail conditions unavailable" />)

    expect(screen.getByText('Trail conditions unavailable')).toBeTruthy()
  })
})

describe('the alerts a hiker has taken off the map (#1047)', () => {
  // A map with the bands hidden and a map with no closure for forty miles are
  // the same picture, and this strip's whole job is to keep those two apart.
  // The legend holds the switch; the legend is shut while somebody is walking.

  it('says so while they are hidden', () => {
    render(<StatusStrip {...PROPS} alertsHidden />)

    expect(screen.getByText('Alerts hidden')).toBeInTheDocument()
  })

  it('says nothing while they are drawn', () => {
    // The ordinary state, and by far the common one. A flag that is always
    // there is a flag nobody reads, which would cost the other eight on this
    // strip their meaning too.
    render(<StatusStrip {...PROPS} />)

    expect(screen.queryByText(/alerts hidden/i)).not.toBeInTheDocument()
  })

  it('keeps saying so with the map in trouble around it', () => {
    // Never stood down for another flag, unlike the two background readings
    // that defer to each other. Those are two readings of one blank screen;
    // this is a second thing missing from it, and a hiker told only "No live
    // map" would have no reason to doubt an empty trail.
    render(
      <StatusStrip
        {...PROPS}
        online={false}
        alertsHidden
        backgroundProblem="live-unreachable"
        trailLinesMissing
      />,
    )

    expect(screen.getByText('Alerts hidden')).toBeInTheDocument()
    expect(screen.getByText('No live map')).toBeInTheDocument()
  })
})
