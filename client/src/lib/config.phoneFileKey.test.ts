// phoneFileKey and V2_PHONE_FILE_KEYS (decision 44, stage 6 of #1793): which
// key a build fetches for each phone file, and the promise that a v2 key is
// fetched only for a file this build has a v2 reader for.

import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  ELEVATION_KEY,
  NEARBY_POI_KEY,
  POI_TYPES,
  REFRESHABLE_KEYS,
  SPURS_KEY,
  TRAILS_KEY,
  TRAIL_MILES_KEY,
  V2_PHONE_FILE_KEYS,
  phoneFileKey,
  poiKey,
} from './config'
import { DATA_SCHEMA_VERSION } from './dataRelease'

describe('phoneFileKey', () => {
  it('keeps every key as v1 has it for a v1 build', () => {
    for (const key of [...V2_PHONE_FILE_KEYS, TRAILS_KEY, SPURS_KEY]) {
      expect(phoneFileKey(key, 'v1')).toBe(key)
    }
  })

  it('puts a file with a v2 under v2/ for a v2 build, and leaves trails.geojson and spurs.json at v1', () => {
    expect(phoneFileKey(ELEVATION_KEY, 'v2')).toBe('v2/elevation_profile.json')
    expect(phoneFileKey(TRAIL_MILES_KEY, 'v2')).toBe('v2/trail_miles.json')
    expect(phoneFileKey(NEARBY_POI_KEY, 'v2')).toBe('v2/nearby_poi.geojson')
    expect(phoneFileKey(poiKey('water'), 'v2')).toBe('v2/poi_water.geojson')
    expect(phoneFileKey(TRAILS_KEY, 'v2')).toBe(TRAILS_KEY)
    expect(phoneFileKey(SPURS_KEY, 'v2')).toBe(SPURS_KEY)
  })

  it('REFRESHABLE_KEYS asks for v2/ keys exactly when DATA_SCHEMA_VERSION is v2', () => {
    // Today v1: pages.yml and ua.yml refuse a build whose channels.json entry
    // for DATA_SCHEMA_VERSION does not resolve, and no v2 release exists yet.
    const schema: string = DATA_SCHEMA_VERSION
    const v2 = REFRESHABLE_KEYS.filter((key) => key.startsWith('v2/'))
    expect(v2.length).toBe(schema === 'v2' ? V2_PHONE_FILE_KEYS.size : 0)
  })

  it('channels.json names a release for DATA_SCHEMA_VERSION in every environment, as the deploy guards require', () => {
    const channels = JSON.parse(
      readFileSync(resolve(process.cwd(), '../channels.json'), 'utf8'),
    ) as Record<string, Record<string, string>>
    for (const [environment, entries] of Object.entries(channels)) {
      expect([environment, typeof entries[DATA_SCHEMA_VERSION]]).toEqual([
        environment,
        'string',
      ])
    }
  })
})

describe('V2_PHONE_FILE_KEYS', () => {
  it('names exactly the files the dbt writers publish a v2/ key for, so every v2 file has a reader here', () => {
    // pipeline/dbt/models/publish/*.yml: each v2 writer's exposure carries
    // `r2_keys: [v2/<file>]`. A v2 file the pipeline writes and this build
    // cannot read, or a v2 key this build asks for and nothing writes, would
    // each be a hiker's missing waypoints or profile.
    const publish = resolve(process.cwd(), '../pipeline/dbt/models/publish')
    const written = new Set<string>()
    for (const name of readdirSync(publish).filter((file) => file.endsWith('.yml'))) {
      const text = readFileSync(resolve(publish, name), 'utf8')
      for (const match of text.matchAll(
        /r2_keys: \[v2\/([a-z0-9_]+\.(?:json|geojson))\]/g,
      )) {
        written.add(match[1])
      }
    }

    expect([...written].sort()).toEqual([...V2_PHONE_FILE_KEYS].sort())
    expect(V2_PHONE_FILE_KEYS.size).toBe(3 + POI_TYPES.length)
  })
})
