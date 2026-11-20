// A challenge map small enough to read, for the map's own tests (#1965).
//
// NOT THE TRAIL. Nine points from Springer Mountain to Katahdin at roughly
// the right places, so a projection and a pin land where a reader expects;
// the real geometry is pipeline/export_challenge_map.py's output, which is
// derived data and is never committed (CLAUDE.md, "A build script's output
// has a home"). Each state is a box, two of them trail states.

import { parseChallengeMap, type ChallengeMap } from './challengeMap'

export const MAP_DOCUMENT = {
  format: 1,
  frame: [-92, 30.5, -62, 49.5],
  trail: [
    {
      coordinates: [
        [-84.19, 34.63],
        [-81.0, 36.5],
        [-79.0, 37.5],
        [-77.7, 39.3],
      ],
      miles: [0, 450, 715, 1026.5],
    },
    {
      coordinates: [
        [-77.6, 39.4],
        [-75.5, 41.0],
        [-73.5, 42.0],
        [-72.0, 43.8],
        [-68.92, 45.9],
      ],
      miles: [1027, 1300, 1500, 1750, 2197.9],
    },
  ],
  states: [
    {
      id: '13',
      name: 'Georgia',
      code: 'GA',
      trail: true,
      label: [-83.5, 33.5],
      polygons: [
        [
          [
            [-85.5, 31],
            [-81, 31],
            [-81, 35],
            [-85.5, 35],
            [-85.5, 31],
          ],
        ],
      ],
    },
    {
      id: '51',
      name: 'Virginia',
      code: 'VA',
      trail: true,
      label: [-78.5, 37.5],
      polygons: [
        [
          [
            [-83.5, 36.5],
            [-76, 36.5],
            [-76, 39.4],
            [-83.5, 39.4],
            [-83.5, 36.5],
          ],
        ],
      ],
    },
    {
      id: '39',
      name: 'Ohio',
      code: null,
      trail: false,
      label: [-82.7, 40.3],
      polygons: [
        [
          [
            [-84.8, 38.4],
            [-80.5, 38.4],
            [-80.5, 42],
            [-84.8, 42],
            [-84.8, 38.4],
          ],
        ],
      ],
    },
  ],
  borders: [
    [
      [-83.5, 36.5],
      [-81, 36.5],
    ],
  ],
  canada: [
    [
      [
        [-80, 45],
        [-70, 45],
        [-70, 49],
        [-80, 49],
        [-80, 45],
      ],
    ],
  ],
  state_runs: [
    ['GA', 0, 78.2],
    ['NC', 78.2, 467.4],
    ['VA', 467.4, 1022.5],
    ['WV', 1022.5, 1027.2],
    ['ME', 1916, 2197.9],
  ],
  credits: [
    { layer: 'trail', source: 'centerline', credit: 'Appalachian Trail Conservancy' },
    { layer: 'states', source: 'us_atlas_states', credit: 'U.S. Census Bureau' },
    { layer: 'canada', source: 'world_atlas_countries', credit: 'Natural Earth' },
  ],
  notices: ['us-atlas and world-atlas: Copyright 2013-2019 Michael Bostock.'],
}

/** The fixture through the real parser, as a phone would hold it. */
export function fixtureMap(): ChallengeMap {
  const map = parseChallengeMap(MAP_DOCUMENT)
  if (map === null) throw new Error('the fixture map no longer parses')
  return map
}
