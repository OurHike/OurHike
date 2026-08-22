import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve as resolvePath } from 'node:path'

import { resolvePoiId, type Tombstones } from './poiIdentity'

// The other half of the two-runtime resolver contract (#831).
//
// features/POI_IDENTITY.md §4 asks for "a resolver, in one place, used by the
// backend's serialisers and the client rather than implemented twice". Across
// Python and TypeScript with no shared package the achievable version is one
// implementation per runtime, each in one file, compared against shared
// fixtures — the pattern three tests in `backend/tests/` already use.
//
// `pipeline/tests/test_export_retired_poi.py` runs these same cases through
// `lib/poi_identity.resolve`. The cases live with the reference implementation
// and are deliberately not restated here: a copy is the third place to keep in
// step, and drift between copies is the bug this arrangement exists to catch.
// `client-tests.yml`'s scope list carries `pipeline/tests/fixtures/`, so
// editing a case runs both suites rather than one.
//
// WHAT THE DERIVATION PROVES, WHICH IS THE POINT OF THIS FILE
//
// The fixture is written as a LEDGER, because that is what the pipeline sees.
// A phone never gets it — it gets the tombstones, which are the retired rows
// alone. Deriving the client's view here rather than hand-writing it is what
// demonstrates the client sees the same world through a smaller artifact
// rather than a different world through a similar one.

interface LedgerRow {
  retired?: string
  superseded_by?: string
}

interface Case {
  name: string
  ledger: Record<string, LedgerRow>
  query: string
  expected: string | null
}

const FIXTURE = resolvePath(
  process.cwd(),
  '../pipeline/tests/fixtures/poi_resolver_cases.json',
)
const cases = (JSON.parse(readFileSync(FIXTURE, 'utf8')) as { cases: Case[] }).cases

/** The tombstones a release would publish from this ledger. */
function tombstonesOf(ledger: Record<string, LedgerRow>): Tombstones {
  const out: Tombstones = {}
  for (const [id, row] of Object.entries(ledger)) {
    if (row.retired === undefined) continue
    out[id] = {
      id,
      poiType: 'shelter',
      source: 'atc_shelters',
      retired: row.retired,
      lon: -74,
      lat: 41,
      ...(row.superseded_by !== undefined ? { supersededBy: row.superseded_by } : {}),
    }
  }
  return out
}

/** What the phone already holds: `poi_*.geojson`, which is the live rows. */
function liveOf(ledger: Record<string, LedgerRow>): (id: string) => boolean {
  const live = new Set(
    Object.entries(ledger)
      .filter(([, row]) => row.retired === undefined)
      .map(([id]) => id),
  )
  return (id) => live.has(id)
}

describe('the shared resolver cases, through this runtime', () => {
  it('found the fixture the pipeline suite reads', () => {
    // Without this the loop below passes by iterating nothing, which is the
    // one way a contract test can be worse than no contract test.
    expect(cases.length).toBeGreaterThanOrEqual(9)
  })

  for (const testCase of cases) {
    it(testCase.name, () => {
      expect(
        resolvePoiId(
          tombstonesOf(testCase.ledger),
          testCase.query,
          liveOf(testCase.ledger),
        ),
      ).toBe(testCase.expected)
    })
  }
})
