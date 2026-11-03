import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { get, set, update } from 'idb-keyval'

import { DeferredMeasureUsage } from './DeferredMeasureUsage'
import { readUsage } from './usageQueue'
import type { UsageMeasurement, UsageMeasurementInput } from './useUsageMeasurement'

// The one piece of usage measurement the first frame carries (#1902): it loads
// the rest behind import(), and holds the one answer that cannot wait for it.

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), update: vi.fn() }))
vi.mock('./api', () => ({
  accessToken: vi.fn(async () => null),
  apiFetch: vi.fn(),
  API_CONFIGURED: false,
}))
vi.mock('./tracePlatform', () => ({ traceShell: () => 'web' }))

let stored: unknown = undefined
beforeEach(() => {
  stored = undefined
  vi.mocked(get).mockImplementation(async () => stored)
  vi.mocked(set).mockImplementation(async (_key, value) => {
    stored = value
  })
  vi.mocked(update).mockImplementation(async (_key, updater) => {
    stored = updater(stored)
  })
})

function input(overrides: Partial<UsageMeasurementInput> = {}): UsageMeasurementInput {
  return {
    ready: true,
    consentSettled: true,
    enabled: true,
    linked: null,
    accountEmail: null,
    newInstall: false,
    version: '1.4.0',
    online: false,
    reportsWaiting: 0,
    screen: 'today',
    mapInView: false,
    gps: { status: 'idle' },
    camera: null,
    trailIndex: null,
    clubRuns: [],
    ...overrides,
  }
}

describe('DeferredMeasureUsage', () => {
  it('renders nothing, and hands App the plan calls once measurement has loaded', async () => {
    const onMeasure = vi.fn<(measurement: UsageMeasurement | null) => void>()

    const { container } = render(
      <DeferredMeasureUsage input={input()} onMeasure={onMeasure} />,
    )

    expect(container).toBeEmptyDOMElement()
    await waitFor(() =>
      expect(onMeasure).toHaveBeenCalledWith(
        expect.objectContaining({ planMade: expect.any(Function) }),
      ),
    )
  })

  it('still counts an install whose hiker skipped first run before measurement arrived', async () => {
    // Fresh install: first run unfinished on the first render with preferences
    // known, then finished by a fast "Skip" before the chunk is in.
    const { rerender } = render(
      <DeferredMeasureUsage input={input({ newInstall: true })} onMeasure={() => {}} />,
    )
    rerender(
      <DeferredMeasureUsage input={input({ newInstall: false })} onMeasure={() => {}} />,
    )

    await waitFor(async () =>
      expect((await readUsage()).rows.map((queued) => queued.row.event)).toEqual([
        'app_installed',
      ]),
    )
  })
})
