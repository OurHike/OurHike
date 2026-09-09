import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  LAUNCH_ARTIFACT_BUDGET_BYTES,
  warnOversized,
  withinLaunchBudget,
} from './artifactBudget'

// The budget's four measurements are the module header's; what this file pins
// is that the number keeps sitting between them. Move it past either side and
// the test says which shipped artifact it now refuses, or which crash it now
// lets through.

afterEach(() => {
  vi.restoreAllMocks()
})

describe('the launch artifact budget (#1254)', () => {
  it('lets through the artifacts phones held before the growth', () => {
    // nearby_trails.geojson decoded, 2026-08-25, and trail_graph_geometry.json
    // decoded, 2026-08-27 - both shipped and neither was reported.
    expect(withinLaunchBudget(23_500_000)).toBe(true)
    expect(withinLaunchBudget(17_285_133)).toBe(true)
  })

  it('refuses the two artifacts that froze and crashed the app on 2026-09-07', () => {
    // trail_graph.json: 9,800 ms of dead main thread. nearby_trails.geojson:
    // the renderer gone at 1,712 MB.
    expect(withinLaunchBudget(78_595_556)).toBe(false)
    expect(withinLaunchBudget(228_820_578)).toBe(false)
  })

  it('is inclusive at the budget and exclusive one byte over', () => {
    expect(withinLaunchBudget(LAUNCH_ARTIFACT_BUDGET_BYTES)).toBe(true)
    expect(withinLaunchBudget(LAUNCH_ARTIFACT_BUDGET_BYTES + 1)).toBe(false)
  })

  it('lets an artifact with no published size through, because unknown is not too large', () => {
    // A manifest written before size_bytes existed must not take the map off
    // a phone. The response is weighed on arrival instead - the loaders' tests
    // hold that half.
    expect(withinLaunchBudget(null)).toBe(true)
  })

  it('says which artifact, how big, and where it was weighed', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)

    warnOversized('trail_graph.json', 78_595_556, 'manifest')

    expect(warn).toHaveBeenCalledTimes(1)
    const line = String(warn.mock.calls[0][0])
    expect(line).toContain('trail_graph.json')
    expect(line).toContain('78595556')
    expect(line).toContain(String(LAUNCH_ARTIFACT_BUDGET_BYTES))
    expect(line).toContain('manifest')
    // The issue number is how a maintainer reading a phone's console gets
    // from the line to the reasoning.
    expect(line).toContain('#1254')
  })
})
