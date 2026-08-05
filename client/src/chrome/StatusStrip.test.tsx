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
    render(<StatusStrip {...PROPS} liveBackgroundUnavailable />)

    expect(screen.getByText(/no live map/i)).toBeInTheDocument()
  })

  it('does not add a second flag for one condition when already offline', () => {
    // "Offline" already accounts for the paper. Two flags saying one thing is
    // noise on a strip this narrow.
    render(<StatusStrip {...PROPS} online={false} liveBackgroundUnavailable />)

    expect(screen.queryByText(/no live map/i)).not.toBeInTheDocument()
    expect(screen.getByText(/offline/i)).toBeInTheDocument()
  })

  it('says when Data Saver is the reason the live map is missing', () => {
    // lib/dataSaver.ts's rule is that the app may override a preference and
    // may not do it silently. Settings said so; the map screen did not, and
    // the map screen is where the override is actually visible - as nothing
    // at all, on a phone with no download.
    render(<StatusStrip {...PROPS} backgroundOverridden />)

    expect(screen.getByText(/data saver/i)).toBeInTheDocument()
  })

  it('stays quiet about the background when nothing is wrong with it', () => {
    render(<StatusStrip {...PROPS} />)

    expect(screen.queryByText(/no live map/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/data saver/i)).not.toBeInTheDocument()
  })
})
