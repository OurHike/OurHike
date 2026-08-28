import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { GpsTraceSettings, elapsedLabel } from './GpsTrace'
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
    // Recording holds the GPS on through a pocket. That is somebody's phone
    // on a mountain, and it is said on the face of the control rather than
    // discovered afterwards.
    renderSection()

    expect(screen.getByText(/more battery than usual/i)).toBeInTheDocument()
    expect(screen.getByText(/in your pocket/i)).toBeInTheDocument()
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
