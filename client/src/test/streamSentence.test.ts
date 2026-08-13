// The stream sentence's wording contract (#529). These assertions lived in
// pipeline/tests/test_lib_poi_description.py while the pipeline composed the
// sentence; they moved here with the composing (#625's split), and the three
// constraints they pin are the load-bearing part of the feature: "mapped as"
// never "is", no flow claim for an unclassified reach, and the no-stream
// fact printed rather than silent.

import { describe, expect, it } from 'vitest'

import { describeStream } from '../lib/streamSentence'

describe('describeStream', () => {
  it('names the stream and qualifies the flow claim, in feet for a feet hiker', () => {
    expect(describeStream({ name: 'Stony Brook', distance_ft: 236.2, flow: 'perennial' }, 'imperial')).toBe(
      'Nearest mapped stream: Stony Brook, about 225 ft (USGS; mapped as year-round, not recently verified).',
    )
  })

  it('writes metres for a metric hiker, from the same published feet', () => {
    expect(describeStream({ name: 'Stony Brook', distance_ft: 236.2, flow: 'perennial' }, 'metric')).toBe(
      'Nearest mapped stream: Stony Brook, about 70 m (USGS; mapped as year-round, not recently verified).',
    )
  })

  it('calls intermittent and ephemeral seasonal, still qualified', () => {
    expect(describeStream({ distance_ft: 1007.2, flow: 'intermittent' }, 'metric')).toBe(
      'Nearest mapped stream about 300 m (USGS; mapped as seasonal, not recently verified).',
    )
    expect(describeStream({ distance_ft: 1007.2, flow: 'ephemeral' }, 'imperial')).toBe(
      'Nearest mapped stream about 1,000 ft (USGS; mapped as seasonal, not recently verified).',
    )
  })

  it('makes no flow claim for an unclassified reach or a class it has never heard of', () => {
    // 46000 is a stream USGS never classified - the sentence says where it
    // is and stops, rather than hedging a claim nobody made. A future flow
    // value degrades the same direction.
    expect(describeStream({ name: 'Matts Creek', distance_ft: 460, flow: 'unclassified' }, 'metric')).toBe(
      'Nearest mapped stream: Matts Creek, about 150 m (USGS).',
    )
    expect(describeStream({ distance_ft: 460, flow: 'braided' }, 'metric')).toBe(
      'Nearest mapped stream about 150 m (USGS).',
    )
  })

  it('rounds coarsely and floors at one step, because "about" must mean it', () => {
    // An envelope query against survey-era geometry is not a measurement:
    // "about 7 ft" would claim precision nobody has, and "about 0" reads as
    // a bug on a streamside shelter.
    expect(describeStream({ distance_ft: 7, flow: 'perennial' }, 'imperial')).toContain('about 25 ft')
    expect(describeStream({ distance_ft: 7, flow: 'perennial' }, 'metric')).toContain('about 10 m')
    expect(describeStream({ distance_ft: 2320, flow: 'perennial' }, 'imperial')).toContain('about 2,300 ft')
    expect(describeStream({ distance_ft: 2320, flow: 'perennial' }, 'metric')).toContain('about 700 m')
  })

  it('prints the no-stream fact in the reader\'s own idiom', () => {
    // Blood Mountain's sentence: a dry ridge is a fact a hiker plans an
    // evening around, and silence would read as the app not knowing.
    expect(describeStream({ none: true }, 'metric')).toBe('No mapped stream within 1 km (USGS).')
    expect(describeStream({ none: true }, 'imperial')).toBe('No mapped stream within 0.6 mi (USGS).')
  })

  it('renders nothing when the artifact published nothing', () => {
    expect(describeStream(undefined, 'metric')).toBeNull()
    expect(describeStream({}, 'imperial')).toBeNull()
  })
})
