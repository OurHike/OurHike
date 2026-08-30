import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {
  GpsTraceSettings,
  backgroundNote,
  elapsedLabel,
  recordingTrouble,
  stalledLabel,
  trailFixNote,
} from './GpsTrace'
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
  lastSampleAt: null,
  lastAccuracyM: null,
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

    expect(screen.getByText(/the screen is not being kept awake/i)).toHaveTextContent(
      /while you stand still without touching it/i,
    )
  })

  it('says the same when the browser refuses on low battery', async () => {
    renderSection({ recording: true, startedAt: 0, samples: 12 }, { wakeLock: 'refused' })

    expect(screen.getByText(/the screen is not being kept awake/i)).toBeInTheDocument()
  })

  it('says the same when the platform takes the lock back mid-walk', async () => {
    // A lock granted at the trailhead and withdrawn at 20% battery leaves the
    // screen sleeping just as surely as one never granted. Anything that is
    // not 'held' has to read the same, or a new state added later quietly
    // starts promising again.
    renderSection(
      { recording: true, startedAt: 0, samples: 12 },
      { wakeLock: 'released' },
    )

    expect(screen.getByText(/the screen is not being kept awake/i)).toBeInTheDocument()
  })

  it('names standing still, because that is when a dark screen is missed', async () => {
    // REPORTED FROM THE THIRD WALK. The old sentence said the recording
    // "pauses every time the screen goes dark", which reads as being about
    // pocketing the phone. The case that actually cost the walk was standing
    // still holding it - not touching it for 45 seconds was enough.
    renderSection(
      { recording: true, startedAt: 0, samples: 12 },
      { wakeLock: 'unsupported' },
    )

    expect(screen.getByText(/stand still without touching it/i)).toBeInTheDocument()
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

  it('says whether the trail columns are being filled', async () => {
    // REPORTED BY THE FIRST FIELD TRACE: `mile`, `off_trail_ft` and
    // `off_tread_ft` came back empty on all 136 rows and this screen had said
    // nothing. Those three columns are the whole reason #93 wants a trace.
    renderSection(
      { recording: true, startedAt: 0, samples: 12 },
      { trailFix: 'recorded' },
    )

    expect(screen.getByText('Trail position')).toBeInTheDocument()
    expect(screen.getByText('recording')).toBeInTheDocument()
  })

  it('names the download when the trail is not on the phone', async () => {
    renderSection(
      { recording: true, startedAt: 0, samples: 12 },
      { trailFix: 'no-trail-data' },
    )

    expect(screen.getByText('trail not downloaded')).toBeInTheDocument()
    expect(screen.getByText(/download it from the map/i)).toBeInTheDocument()
  })

  it('names the distance when the walk is nowhere near the trail', async () => {
    renderSection(
      { recording: true, startedAt: 0, samples: 12 },
      { trailFix: 'off-corridor' },
    )

    expect(screen.getByText('not near the trail')).toBeInTheDocument()
    expect(screen.getByText(/more than three miles/i)).toBeInTheDocument()
  })

  it('tells the two blanks apart, because they need different things done', async () => {
    // A boolean here would be the empty column all over again: same blank, and
    // one is fixed by a download and the other only by walking somewhere else.
    expect(trailFixNote('no-trail-data')).not.toBe(trailFixNote('off-corridor'))
  })

  it('says a recording has stalled, which no count could', async () => {
    // THE THIRD WALK'S DEFECT. Fixes stopped and the tester stood still for
    // several more minutes beside a recording that had already ended - the
    // count was on screen the whole time, and a count that has stopped
    // climbing looks exactly like one climbing slowly.
    renderSection(
      { recording: true, startedAt: 0, samples: 136, lastSampleAt: 0 },
      { now: new Date(272_000) },
    )

    expect(screen.getByText(/no reading for 4 minutes/i)).toBeInTheDocument()
  })

  it('tells the tester what to do about a stall, not just that there is one', async () => {
    renderSection(
      { recording: true, startedAt: 0, samples: 136, lastSampleAt: 0 },
      { now: new Date(272_000) },
    )

    expect(screen.getByText(/wake the phone/i)).toHaveTextContent(
      /nothing already recorded is lost/i,
    )
  })

  it('stays quiet through the gaps a stationary phone actually produces', async () => {
    // 150.2 s was the largest gap in 39 minutes of a HEALTHY stationary
    // recording (the fourth field trace, wake_lock 'held' and page_visible
    // 'yes' on every row). A warning there is a warning nobody reads by the
    // second hour.
    renderSection(
      { recording: true, startedAt: 0, samples: 136, lastSampleAt: 0 },
      { now: new Date(150_200) },
    )

    expect(screen.queryByText(/no reading for/i)).not.toBeInTheDocument()
  })

  it('says nothing about a stall once the recording is stopped', async () => {
    // A finished trace is not stalled, and every saved trace would trip a
    // naive age check the moment it was stopped.
    renderSection(
      { recording: false, samples: 136, startedAt: 0, lastSampleAt: 0 },
      {
        now: new Date(600_000),
      },
    )

    expect(screen.queryByText(/no reading for/i)).not.toBeInTheDocument()
  })

  it('offers the screen-off switch before the walk, not during it', async () => {
    // A decision about the walk: flipped mid-recording it would leave half
    // the trace measuring one watch and half the other.
    const onBackgroundChange = vi.fn()
    renderSection({}, { onBackgroundChange })

    await userEvent.click(
      screen.getByRole('checkbox', { name: /keep recording with the screen off/i }),
    )

    expect(onBackgroundChange).toHaveBeenCalledWith(true)
  })

  it('warns that the two watches measure differently, before anything is on', async () => {
    // The 68% vs 95% trap, in words a volunteer can act on. Said before the
    // switch is flipped, because afterwards it is a caveat on a file.
    renderSection({}, { onBackgroundChange: vi.fn() })

    expect(screen.getByText(/measured slightly differently/i)).toHaveTextContent(
      /records which is which/i,
    )
  })

  it('does not offer the switch at all when the shell cannot do it', async () => {
    renderSection()

    expect(
      screen.queryByRole('checkbox', { name: /keep recording with the screen off/i }),
    ).not.toBeInTheDocument()
  })

  it('says a browser cannot do this without calling it broken', async () => {
    // The PR preview IS a browser, and it is where every field test so far
    // has happened. Telling a tester the app is broken when they are simply
    // on the preview link is how a tester stops reading this screen.
    renderSection(
      {},
      { onBackgroundChange: vi.fn(), backgroundWanted: true, background: 'not-native' },
    )

    expect(screen.getByText(/only works in the installed app/i)).toBeInTheDocument()
  })

  it('shows whether a screen-off recording actually took', async () => {
    renderSection(
      { recording: true, startedAt: 0, samples: 12 },
      { backgroundWanted: true, background: 'on' },
    )

    expect(screen.getByText('Screen off')).toBeInTheDocument()
    expect(screen.getByText('still recording')).toBeInTheDocument()
  })

  it('says the recording will pause when the switch is on but the watch is not', async () => {
    renderSection(
      { recording: true, startedAt: 0, samples: 12 },
      { backgroundWanted: true, background: 'not-authorized' },
    )

    expect(screen.getByText('recording pauses')).toBeInTheDocument()
  })

  it('says nothing about screen-off recording when it was never asked for', async () => {
    renderSection({ recording: true, startedAt: 0, samples: 12 })

    expect(screen.queryByText('Screen off')).not.toBeInTheDocument()
  })

  it('prints what the last reading actually claimed', async () => {
    // THE FIFTH FIELD TRACE. One reading in 74 minutes, stating exactly 100 m
    // with no speed and no heading - a network fix, not GNSS. Nothing on this
    // screen said so, so the tester stood there waiting for a satellite lock
    // that had never happened.
    renderSection({ recording: true, startedAt: 0, samples: 1, lastAccuracyM: 100 })

    expect(screen.getByText('Last reading')).toBeInTheDocument()
    // Through lib/units.ts like every other distance a hiker reads, so it
    // comes out in the system they chose. 100 m is about 328 ft.
    expect(screen.getByText(/give or take 328 ft/i)).toBeInTheDocument()
  })

  it('reads that figure in the system the hiker chose', async () => {
    renderSection(
      { recording: true, startedAt: 0, samples: 1, lastAccuracyM: 100 },
      { units: 'metric' },
    )

    expect(screen.getByText(/give or take 100 m/i)).toBeInTheDocument()
  })

  it('asserts no threshold on that number, because none has been validated', async () => {
    // A figure, not a verdict. Calling 100 m "poor" would be inventing the
    // boundary this whole branch exists to go and measure.
    renderSection({ recording: true, startedAt: 0, samples: 1, lastAccuracyM: 100 })

    expect(screen.queryByText(/poor|bad|weak|inaccurate/i)).not.toBeInTheDocument()
  })

  it('says nothing about accuracy before the first reading', async () => {
    renderSection({ recording: true, startedAt: 0, samples: 0 })

    expect(screen.queryByText('Last reading')).not.toBeInTheDocument()
  })

  it('shows how many readings were asked for and how many arrived', async () => {
    // A poll that times out writes no row, so without this "the poll is not
    // working" and "the poll never ran" look identical in the exported file.
    renderSection(
      { recording: true, startedAt: 0, samples: 1 },
      { polls: { asked: 888, answered: 0 } },
    )

    expect(screen.getByText('Readings asked for')).toBeInTheDocument()
    expect(screen.getByText(/0 of 888 answered/)).toBeInTheDocument()
  })

  it('says nothing about polling before anything has been asked', async () => {
    renderSection(
      { recording: true, startedAt: 0, samples: 1 },
      { polls: { asked: 0, answered: 0 } },
    )

    expect(screen.queryByText('Readings asked for')).not.toBeInTheDocument()
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

describe('backgroundNote', () => {
  it('says nothing while it is off or working', () => {
    expect(backgroundNote('off')).toBeNull()
    expect(backgroundNote('on')).toBeNull()
  })

  it('calls a browser a browser rather than a failure', () => {
    expect(backgroundNote('not-native')).toMatch(/only works in the installed app/i)
    expect(backgroundNote('not-native')).not.toMatch(/error|failed|broken/i)
  })

  it('names the settings screen, because the app genuinely cannot ask', () => {
    // ACCESS_BACKGROUND_LOCATION cannot be granted from an in-app prompt on
    // Android 10+. A note saying "grant permission" would send a tester
    // looking for a dialog that will never appear.
    expect(backgroundNote('not-authorized')).toMatch(/allow all the time/i)
    expect(backgroundNote('not-authorized')).toMatch(/own settings/i)
  })

  it('admits it does not know, rather than inventing a cause', () => {
    expect(backgroundNote('failed')).toMatch(/did not say why/i)
  })

  it('says what still works in every failing case', () => {
    // None of these stop the recording. A note that read as total failure
    // would send a tester home mid-walk.
    for (const state of ['not-native', 'not-authorized', 'failed'] as const) {
      expect(backgroundNote(state)).toMatch(/still runs while the screen is on/i)
    }
  })
})

describe('stalledLabel', () => {
  const NOW = new Date(10_000_000)
  const secondsAgo = (s: number) => NOW.getTime() - s * 1000

  it('says nothing before the first reading', () => {
    expect(stalledLabel(null, NOW, true)).toBeNull()
  })

  it('says nothing at the ordinary walking cadence', () => {
    expect(stalledLabel(secondsAgo(6), NOW, true)).toBeNull()
  })

  it('stays quiet through every gap a healthy stationary phone produced', () => {
    // THE FOURTH FIELD TRACE, and the reason this threshold moved from 60 s.
    // 39 minutes of standing still with wake_lock 'held' and page_visible
    // 'yes' on all 34 rows - screen awake, page running, and the platform
    // simply sending fewer fixes to a phone that was not moving. At 60 s this
    // warning fired six times, five of them at a recording working perfectly.
    for (const gap of [
      5.6, 11.3, 17, 25, 28.2, 49.5, 59.7, 63, 68.7, 93.8, 98.7, 150.2,
    ]) {
      expect(stalledLabel(secondsAgo(gap), NOW, true)).toBeNull()
    }
  })

  it('still catches the silence that cost the third walk', () => {
    // 272 s, which is the whole point of the control existing.
    expect(stalledLabel(secondsAgo(272), NOW, true)).toMatch(/4 minutes/)
  })

  it('does not diagnose a dark screen, because that is often wrong', () => {
    // The old sentence said "the screen probably went dark". The fourth trace
    // shows fixes thinning on a stationary phone with the screen fully awake,
    // so telling a standing tester their screen died sends them to fix
    // something that is not broken.
    const label = stalledLabel(secondsAgo(600), NOW, true)
    expect(label).toMatch(/if you are standing still that can be normal/i)
    expect(label).toMatch(/if you are walking/i)
  })

  it('says nothing when nothing is recording', () => {
    expect(stalledLabel(secondsAgo(600), NOW, false)).toBeNull()
  })
})

describe('trailFixNote', () => {
  it('says nothing while the trail columns are filling', () => {
    // The status row already says "recording"; a note agreeing with it is the
    // caveat on every screen that reads like a caveat on none.
    expect(trailFixNote('recorded')).toBeNull()
  })

  it('says nothing before the first fix has arrived', () => {
    expect(trailFixNote('waiting')).toBeNull()
  })

  it('calls a walk off the corridor useful rather than broken', () => {
    // Walking a mile from the house to shake the recorder out is a reasonable
    // thing to do with this, and it still collects every accuracy reading the
    // readout change needs. Telling a tester they have wasted the afternoon
    // when they have not is how a tester stops reading this screen.
    expect(trailFixNote('off-corridor')).toMatch(/still a useful recording/i)
  })

  it('says what is still being recorded in both failing cases', () => {
    for (const state of ['no-trail-data', 'off-corridor'] as const) {
      expect(trailFixNote(state)).toMatch(/everything else is/i)
    }
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
