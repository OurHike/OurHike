import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { GpsTraceSettings, elapsedLabel, recordingTrouble } from './GpsTrace'
import type { TraceStatus } from '../lib/gpsTrace'

// The switch a volunteer taps in the rain. Two things are being tested: that
// the battery cost and the privacy boundary are said before anything is
// recorded, and that the markers - the part that makes the trace worth
// taking at all - are reachable while it runs.

const IDLE: TraceStatus = {
  recording: false,
  startedAt: null,
  marker: null,
  samples: 0,
}

afterEach(() => {
  // This project does not auto-clean between renders (see Settings.test.tsx).
  // Left out, every query below matches the previous test's markup too.
  cleanup()
})

function renderSection(status: Partial<TraceStatus> = {}, overrides = {}) {
  const props = {
    status: { ...IDLE, ...status },
    onStart: vi.fn(),
    onStop: vi.fn(),
    onMark: vi.fn(),
    onExport: vi.fn(),
    onDelete: vi.fn(),
    now: new Date(1_000_000),
    ...overrides,
  }
  render(<GpsTraceSettings {...props} />)
  return props
}

describe('GpsTraceSettings', () => {
  it('says what it costs before anything is recording', async () => {
    // That is somebody's phone on a mountain, and it is said on the face of
    // the control rather than discovered afterwards.
    renderSection()

    expect(screen.getByText(/a lot more battery than usual/i)).toBeInTheDocument()
    expect(screen.getByText(/the screen is most of that/i)).toBeInTheDocument()
  })

  it('does not promise recording through a locked phone', async () => {
    // THE REGRESSION THIS FILE EXISTS TO STOP COMING BACK. The first version
    // said "including while the phone is in your pocket", a real walk found it
    // false, and a tester who believes it walks ninety minutes and comes back
    // with twenty. A web app cannot record through a locked screen.
    renderSection()

    expect(screen.queryByText(/in your pocket/i)).not.toBeInTheDocument()
    expect(screen.getByText(/if you lock the phone yourself/i)).toHaveTextContent(
      /pauses until you unlock it/i,
    )
  })

  it('promises nothing is lost across that pause', async () => {
    renderSection()

    expect(screen.getByText(/nothing already recorded is lost/i)).toBeInTheDocument()
  })

  it('says where the recording goes, which is nowhere', async () => {
    renderSection()

    const note = screen.getByText(/stays on this phone/i)
    expect(note).toHaveTextContent(/never uploaded/i)
    expect(note).toHaveTextContent(/never attached to a problem report/i)
  })

  it('starts recording when asked', async () => {
    const props = renderSection()

    await userEvent.click(screen.getByRole('button', { name: 'Start recording' }))

    expect(props.onStart).toHaveBeenCalledOnce()
  })

  it('offers no markers before recording, so the screen stays one decision', async () => {
    renderSection()

    expect(screen.queryByRole('button', { name: 'Walking' })).not.toBeInTheDocument()
  })

  it('offers all three markers while recording', async () => {
    renderSection({ recording: true, startedAt: 0, samples: 12 })

    for (const label of ['Standing still', 'Walking', 'Off the trail']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
  })

  it('marks what the hiker says they are doing', async () => {
    const props = renderSection({ recording: true, startedAt: 0, samples: 12 })

    await userEvent.click(screen.getByRole('button', { name: 'Off the trail' }))

    expect(props.onMark).toHaveBeenCalledWith('off-trail')
  })

  it('shows which marker is standing, so a tap is confirmed', async () => {
    // A hiker who cannot tell whether the tap registered taps again, and the
    // recording is the only place that answer exists.
    renderSection({ recording: true, startedAt: 0, samples: 12, marker: 'walking' })

    expect(screen.getByRole('button', { name: 'Walking' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: 'Standing still' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  it('says why the markers matter, in the second person', async () => {
    renderSection({ recording: true, startedAt: 0, samples: 12 })

    expect(
      screen.getByText(/standing still under trees and a slow walk/i),
    ).toBeInTheDocument()
  })

  it('counts the readings so a tester can see it is working', async () => {
    renderSection({ recording: true, startedAt: 0, samples: 1284 })

    expect(screen.getByText(/1,284 readings/)).toBeInTheDocument()
  })

  it('says the screen is being held while the lock is held', async () => {
    renderSection({ recording: true, startedAt: 0, samples: 12 }, { wakeLock: 'held' })

    expect(screen.getByText(/screen is being kept awake/i)).toBeInTheDocument()
  })

  it('says the screen will sleep when the browser has no wake lock', async () => {
    // A tester whose screen is going to sleep anyway needs that DURING the
    // walk, when lengthening the screen timeout is still an option.
    renderSection(
      { recording: true, startedAt: 0, samples: 12 },
      { wakeLock: 'unsupported' },
    )

    expect(screen.getByText(/will not let the screen stay awake/i)).toBeInTheDocument()
  })

  it('says the same when the browser refuses on low battery', async () => {
    renderSection({ recording: true, startedAt: 0, samples: 12 }, { wakeLock: 'refused' })

    expect(screen.getByText(/will not let the screen stay awake/i)).toBeInTheDocument()
  })

  it('says why a recording is empty rather than showing a bare zero', async () => {
    // REPORTED FROM A REAL WALK: recording ran, stored zero points, and this
    // screen said "Recording · 0 readings" and nothing else. The watch had
    // known all along; this section never looked.
    renderSection({ recording: true, startedAt: 0, samples: 0 }, { gpsStatus: 'denied' })

    expect(screen.getByText(/blocking location for this site/i)).toBeInTheDocument()
  })

  it('stays quiet about trouble once readings are arriving', async () => {
    // A caveat on every screen reads exactly like a caveat on none. A count
    // that is climbing says it better.
    renderSection(
      { recording: true, startedAt: 0, samples: 412 },
      { gpsStatus: 'located' },
    )

    expect(screen.queryByText(/waiting for the first reading/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/no gps signal right now/i)).not.toBeInTheDocument()
  })

  it('stops when asked', async () => {
    const props = renderSection({ recording: true, startedAt: 0, samples: 12 })

    await userEvent.click(screen.getByRole('button', { name: 'Stop recording' }))

    expect(props.onStop).toHaveBeenCalledOnce()
  })

  it('offers no export while there is nothing recorded', async () => {
    renderSection()

    expect(
      screen.queryByRole('button', { name: /save the recording/i }),
    ).not.toBeInTheDocument()
  })

  it('offers the export once a trace has been stopped', async () => {
    const props = renderSection({ samples: 400, startedAt: 0 })

    await userEvent.click(screen.getByRole('button', { name: /save the recording/i }))

    expect(props.onExport).toHaveBeenCalledOnce()
  })

  it('hides the export while still recording, so a partial file is not mistaken for the walk', async () => {
    renderSection({ recording: true, startedAt: 0, samples: 400 })

    expect(
      screen.queryByRole('button', { name: /save the recording/i }),
    ).not.toBeInTheDocument()
  })

  it('will not delete on one press', async () => {
    const props = renderSection({ samples: 400, startedAt: 0 })

    await userEvent.click(screen.getByRole('button', { name: /^delete the recording$/i }))

    expect(props.onDelete).not.toHaveBeenCalled()
    expect(screen.getByText(/it is gone/i)).toBeInTheDocument()
  })

  it('deletes on the second press', async () => {
    const props = renderSection({ samples: 400, startedAt: 0 })

    await userEvent.click(screen.getByRole('button', { name: /^delete the recording$/i }))
    await userEvent.click(screen.getByRole('button', { name: /yes, delete it/i }))

    expect(props.onDelete).toHaveBeenCalledOnce()
  })

  it('lets the hiker back out of deleting', async () => {
    const props = renderSection({ samples: 400, startedAt: 0 })

    await userEvent.click(screen.getByRole('button', { name: /^delete the recording$/i }))
    await userEvent.click(screen.getByRole('button', { name: /keep it/i }))

    expect(props.onDelete).not.toHaveBeenCalled()
    expect(
      screen.getByRole('button', { name: /^delete the recording$/i }),
    ).toBeInTheDocument()
  })
})

describe('recordingTrouble', () => {
  // Every branch names something the tester can act on, because a walk that
  // comes back empty has already cost the afternoon.

  it('names the permission when the browser is blocking it', () => {
    expect(recordingTrouble('denied', 0)).toMatch(/allow it in the site settings/i)
  })

  it('says a browser without GPS cannot record at all', () => {
    expect(recordingTrouble('unsupported', 0)).toMatch(/cannot do gps at all/i)
  })

  it('calls a lost signal normal rather than an error', () => {
    // Losing signal under cover is an ordinary condition on trail. Saying it
    // is broken would send a tester home mid-walk.
    expect(recordingTrouble('unavailable', 120)).toMatch(/that is normal indoors/i)
  })

  it('tells a tester what to do while the count is still zero', () => {
    expect(recordingTrouble('located', 0)).toMatch(/step into the open/i)
  })

  it('says nothing once readings are arriving', () => {
    expect(recordingTrouble('located', 1)).toBeNull()
  })

  it('reports trouble even with readings already banked', () => {
    // A recording that collected 400 points and then lost the signal is still
    // collecting nothing NOW, which is what the tester needs to know.
    expect(recordingTrouble('denied', 400)).not.toBeNull()
    expect(recordingTrouble('unavailable', 400)).not.toBeNull()
  })
})

describe('elapsedLabel', () => {
  it('says nothing before a recording has started', () => {
    expect(elapsedLabel(null, new Date(1_000_000))).toBe('')
  })

  it('reads as just started under a minute', () => {
    expect(elapsedLabel(1_000_000, new Date(1_030_000))).toBe('just started')
  })

  it('does not pluralise one minute', () => {
    expect(elapsedLabel(1_000_000, new Date(1_060_000))).toBe('1 minute')
  })

  it('counts whole minutes, never seconds', () => {
    // A counter ticking every second keeps the screen awake, on the one
    // feature here that already costs battery deliberately.
    expect(elapsedLabel(1_000_000, new Date(1_000_000 + 21 * 60_000 + 42_000))).toBe(
      '21 minutes',
    )
  })
})
