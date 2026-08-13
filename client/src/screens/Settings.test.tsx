import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Settings } from './Settings'
import { BACKGROUND_SOURCES, DEFAULT_PREFERENCES } from '../lib/userPreferences'
import { HIDEABLE_TYPES } from '../lib/waypointVisibility'

// WIREFRAMES.md §10. Five groups, one canonical UserPreferences model.
//
// The account row landed in Phase E5. Signing out must never destroy what is
// on the phone: the map, the outbox and the preferences are all local first
// and an account only syncs them (IDENTITY_AND_PRIVACY.md). An app that wiped
// a queued report because someone signed out would be losing work they had
// no reason to think was at risk.
//
// The schema-level guarantee that no closures/warnings toggle can exist lives
// in lib/userPreferences.test.ts, where TESTING.md item 16 says to put it.
// What is tested here is the visible half: the locked red callout that tells
// someone why they cannot find the switch they went looking for.

const PROPS = {
  account: null as { email: string } | null,
  onSignIn: vi.fn(),
  onSignOut: vi.fn(),
  preferences: DEFAULT_PREFERENCES,
  onChange: vi.fn(),
  lastSyncedAt: new Date('2026-07-29T09:00:00Z'),
  onSync: vi.fn(),
  onExport: vi.fn(),
}

const live = { ...DEFAULT_PREFERENCES, background_source: 'hiking_topo_live' as const }
const offline = {
  ...DEFAULT_PREFERENCES,
  background_source: 'usgs_topo_offline' as const,
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

/** Settings with the props overridden, for the tests that care about one of
 *  them - the file otherwise spreads PROPS directly. */
function renderSettings(overrides: Partial<typeof PROPS>) {
  return render(<Settings {...PROPS} {...overrides} />)
}

describe('Settings', () => {
  it('lays out the groups WIREFRAMES.md names', () => {
    render(<Settings {...PROPS} />)

    for (const group of ['You', 'The map', 'Display', 'Safety & privacy', 'Your data']) {
      expect(screen.getByRole('heading', { name: group })).toBeInTheDocument()
    }
  })

  // #378. Settings is where somebody goes looking for it, and it is the only
  // screen a hiker can reach that could carry it - so the wiring is worth a
  // test of its own even though screens/AboutBuild.test.tsx covers the rows.
  it('says which build the app is running, without being passed one', () => {
    render(<Settings {...PROPS} />)

    const about = screen.getByRole('heading', { name: 'About this build' })
    expect(about).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /copy build details/i }),
    ).toBeInTheDocument()
  })

  it('states that closures and serious warnings are always shown', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getByText(/always shown/i)).toHaveTextContent(
      /closures and serious warnings/i,
    )
  })

  it('says the absence of a switch is deliberate, not an oversight', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getByText(/no switch, here or anywhere/i)).toBeInTheDocument()
  })

  it('renders no control at all for closures or warnings', () => {
    render(<Settings {...PROPS} />)
    const toggles = screen
      .getAllByRole('checkbox')
      .map((el) => el.getAttribute('name') ?? '')

    expect(toggles.filter((name) => /closure|warning/i.test(name))).toEqual([])
  })

  it('writes a map style change as a preference patch', async () => {
    const user = userEvent.setup()
    render(<Settings {...PROPS} />)

    await user.click(screen.getByRole('radio', { name: /night hike/i }))

    expect(PROPS.onChange).toHaveBeenCalledWith({ map_style: 'night_hike' })
  })

  it('writes a detail change as a preference patch', async () => {
    const user = userEvent.setup()
    render(<Settings {...PROPS} />)

    await user.click(screen.getByRole('radio', { name: /minimal/i }))

    expect(PROPS.onChange).toHaveBeenCalledWith({ layer_detail_level: 'minimal' })
  })

  it('offers red light only while night_hike is chosen', () => {
    // Under Field the toggle would change nothing - the sub-mode refines
    // night_hike only (map/liveTopo.ts sheetPalette) - and a live-looking
    // control with no effect is the dishonesty the Later rows exist to avoid.
    render(<Settings {...PROPS} />)

    expect(screen.queryByRole('checkbox', { name: /red light/i })).toBeNull()
  })

  it('writes the red-light toggle once night_hike is chosen', async () => {
    const user = userEvent.setup()
    render(
      <Settings
        {...PROPS}
        preferences={{ ...DEFAULT_PREFERENCES, map_style: 'night_hike' }}
      />,
    )

    await user.click(screen.getByRole('checkbox', { name: /red light/i }))

    expect(PROPS.onChange).toHaveBeenCalledWith({ red_light_enabled: true })
  })

  it('shows the wrong-way alert as Later, because nothing implements it yet', () => {
    // The preference is real (lib/userPreferences.ts) but the feature is not:
    // no monitor runs, no cue mounts, no push fires. A live-looking switch
    // here told a hiker an alarm was armed when there is no alarm - the worst
    // kind of safety copy. The row stays visible so the answer to "is there a
    // wrong-way alert?" is an honest "later", not a hunt through screens.
    render(<Settings {...PROPS} />)
    const toggle = screen.getByRole('checkbox', { name: /wrong-way alert.*later/i })

    expect(toggle).toBeDisabled()
    expect(toggle).not.toBeChecked()
  })

  it('never reports a wrong-way preference change, since no tap can happen', async () => {
    const user = userEvent.setup()
    render(<Settings {...PROPS} />)

    await user.click(screen.getByRole('checkbox', { name: /wrong-way alert.*later/i }))

    expect(PROPS.onChange).not.toHaveBeenCalled()
  })

  // Scoped to the Background group rather than to every radio on the screen.
  // There is a second group now - Light / Dark / Auto (ThemePicker.tsx) - and
  // an unscoped getAllByRole('radio') collected both, which is how a test
  // about backgrounds started asserting that "auto" is one.
  const backgroundRadios = () =>
    within(screen.getByRole('group', { name: /background/i })).getAllByRole('radio')

  it('offers the background as a real control, on the canonical field name', () => {
    // A radio group since 2026-08-05, not a select - the same component the
    // legend shows, so the two cannot drift. The canonical field name is still
    // what the inputs are grouped by.
    render(<Settings {...PROPS} />)
    const radios = backgroundRadios()

    expect(radios.length).toBeGreaterThan(0)
    for (const radio of radios) {
      expect(radio).toHaveAttribute('name', 'settings-background_source')
    }
    const checked = radios.find((r) => (r as HTMLInputElement).checked)
    expect((checked as HTMLInputElement).value).toBe(PROPS.preferences.background_source)
  })

  it('offers exactly the backgrounds the map can actually draw', () => {
    render(<Settings {...PROPS} />)
    const values = backgroundRadios().map((radio) => (radio as HTMLInputElement).value)

    expect(values.sort()).toEqual([...BACKGROUND_SOURCES].sort())
  })

  it('reports a background change against the canonical field name', async () => {
    const user = userEvent.setup()
    render(<Settings {...PROPS} />)

    await user.click(screen.getByRole('radio', { name: /downloaded/i }))

    expect(PROPS.onChange).toHaveBeenCalledWith({
      background_source: 'usgs_topo_offline',
    })
  })

  it('routes the background choice through the shell when it is given one', async () => {
    // Choosing "downloaded" can mean more than storing a preference - with
    // nothing on the phone it opens the download window (App.tsx) - and the
    // shell can only apply that rule if the choice reaches it.
    const user = userEvent.setup()
    const onChangeBackground = vi.fn()
    render(<Settings {...PROPS} onChangeBackground={onChangeBackground} />)

    await user.click(screen.getByRole('radio', { name: /downloaded/i }))

    expect(onChangeBackground).toHaveBeenCalledWith('usgs_topo_offline')
    expect(PROPS.onChange).not.toHaveBeenCalled()
  })

  it('offers the way to the download, since there is no tab to send anyone to', async () => {
    const user = userEvent.setup()
    const onOpenDownloads = vi.fn()
    render(<Settings {...PROPS} onOpenDownloads={onOpenDownloads} />)

    await user.click(screen.getByRole('button', { name: /choose what to download/i }))

    expect(onOpenDownloads).toHaveBeenCalledTimes(1)
  })

  it('admits a download still running with its window shut', () => {
    // The other home of the same link, and the screen someone comes back to
    // an hour later to ask whether the thing they started ever finished.
    render(
      <Settings
        {...PROPS}
        onOpenDownloads={vi.fn()}
        downloadActivity={{ kind: 'downloading', doneBytes: 1, totalBytes: 4 }}
      />,
    )

    expect(screen.getByText('Downloading 25%')).toBeVisible()
  })

  it('puts it at the foot of the screen, below every group', async () => {
    // A once-a-season errand, so it is findable by anyone who scrolls looking
    // for it and out of the way of the rows that get used.
    const { container } = render(<Settings {...PROPS} onOpenDownloads={vi.fn()} />)

    const link = screen.getByRole('button', { name: /choose what to download/i })
    expect(container.querySelector('.settings')?.lastElementChild).toBe(link)
  })

  it('says the live background still falls back to the download with no signal', () => {
    // The one thing someone choosing between these actually needs to know, and
    // the one thing a provider name would not tell them.
    render(<Settings {...PROPS} preferences={live} />)

    expect(screen.getByText(/no signal/i)).toBeInTheDocument()
  })

  it('tells the hiker when Data Saver has overridden their background choice', () => {
    // The override is defensible; doing it while this screen still claims the
    // live sheet is on would not be. This notice is the only place someone
    // would go to find out why the map suddenly looks different, so it is
    // asserted here rather than left to the map to imply.
    // `archiveDownloaded` because Data Saver only subtracts once there is a
    // download to fall back on - see lib/dataSaver.ts. Without one the map
    // draws the live sheet regardless, and this notice would be false.
    render(<Settings {...PROPS} preferences={live} dataSaver archiveDownloaded />)

    expect(screen.getByText(/data saver is on/i)).toBeInTheDocument()
  })

  it('says how to get the live sheet back, not just that it is gone', () => {
    render(<Settings {...PROPS} preferences={live} dataSaver archiveDownloaded />)

    expect(screen.getByText(/turn data saver off/i)).toBeInTheDocument()
  })

  it('does not blame Data Saver when the real reason is an empty phone', () => {
    // Data Saver is on and being ignored, because "downloaded only" has no
    // download to draw. Saying "Data Saver is on, so the map is using your
    // download only" would be false twice over: it is not, and there is none.
    render(<Settings {...PROPS} preferences={offline} dataSaver />)

    expect(screen.queryByText(/data saver is on/i)).not.toBeInTheDocument()
    expect(screen.getByText(/nothing is downloaded yet/i)).toBeInTheDocument()
  })

  it('explains that an offline choice waits for a download to honour it', () => {
    render(<Settings {...PROPS} preferences={offline} />)

    expect(
      screen.getByText(/download the map and this setting takes effect/i),
    ).toBeInTheDocument()
  })

  it('stays quiet when Data Saver merely agrees with what was already picked', () => {
    // Not an override - telling someone their preference was overridden when
    // it was honoured is its own small lie.
    render(<Settings {...PROPS} preferences={offline} dataSaver archiveDownloaded />)

    expect(screen.queryByText(/data saver is on/i)).not.toBeInTheDocument()
  })

  it('stays quiet when nothing is overriding anything', () => {
    render(<Settings {...PROPS} preferences={live} />)

    expect(screen.queryByText(/data saver is on/i)).not.toBeInTheDocument()
  })

  it('says the offline background fetches nothing, which is why anyone picks it', () => {
    render(<Settings {...PROPS} preferences={offline} />)

    expect(screen.getByText(/no background data is fetched/i)).toBeInTheDocument()
  })

  it('tags not-yet-built rows "Later" rather than hiding them', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getAllByText('Later').length).toBeGreaterThan(0)
  })

  // #619. Units was the standing example of the "Later" treatment - a disabled
  // checkbox over a preference key that had a backend column, a sync payload
  // and nothing at all reading it. These three assert the row is now a control
  // that writes, because the tag it shed is only honest while it is temporary.
  it('offers units as a live control rather than a Later row', () => {
    render(<Settings {...PROPS} />)

    const units = within(screen.getByRole('group', { name: /units/i }))
    for (const radio of units.getAllByRole('radio')) {
      expect(radio).toBeEnabled()
    }
  })

  it('writes the unit choice to the canonical preference key', async () => {
    const user = userEvent.setup()
    render(<Settings {...PROPS} />)

    await user.click(screen.getByRole('radio', { name: /metres/i }))

    expect(PROPS.onChange).toHaveBeenCalledWith({ unit_system: 'metric' })
  })

  it('shows the stored choice, so the screen agrees with what the app is doing', () => {
    renderSettings({
      preferences: { ...DEFAULT_PREFERENCES, unit_system: 'metric' },
    })

    expect(screen.getByRole('radio', { name: /metres/i })).toBeChecked()
  })

  it('disables the Later rows so they cannot be operated', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getByRole('checkbox', { name: /roads & walkability/i })).toBeDisabled()
  })

  it('offers sign-in when signed out', async () => {
    const user = userEvent.setup()
    render(<Settings {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(PROPS.onSignIn).toHaveBeenCalled()
  })

  it('shows the account and offers sign-out when signed in', async () => {
    const user = userEvent.setup()
    render(<Settings {...PROPS} account={{ email: 'pat@example.org' }} />)

    expect(screen.getByText('pat@example.org')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /sign out/i }))

    expect(PROPS.onSignOut).toHaveBeenCalled()
  })

  it('says the trail name lives only on this device while signed out', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getByText(/on this device/i)).toBeInTheDocument()
  })

  it('says the trail name is linked once an account exists', () => {
    render(
      <Settings
        {...PROPS}
        account={{ email: 'pat@example.org' }}
        preferences={{ ...DEFAULT_PREFERENCES, trail_name: 'Switchback' }}
      />,
    )

    expect(screen.getByText(/linked/i)).toBeInTheDocument()
  })

  it('promises signing out keeps the map, the outbox and the settings', () => {
    // The assurance that matters most on this screen. Someone who believes
    // signing out might discard a queued report simply will not sign out.
    render(<Settings {...PROPS} account={{ email: 'pat@example.org' }} />)

    expect(
      screen.getByText(/stays on this phone|nothing is deleted/i),
    ).toBeInTheDocument()
  })

  it('shows the reporter type reports are signed with', () => {
    render(
      <Settings
        {...PROPS}
        preferences={{ ...DEFAULT_PREFERENCES, reporter_type: 'thru' }}
      />,
    )

    expect(screen.getByRole('combobox', { name: /signed as/i })).toHaveValue('thru')
  })

  it('says "Not set" rather than a type nobody chose (#233)', () => {
    // The bug: every report was filed as `thru` from a hardcoded literal, so
    // this row showed a claim its owner had never made. Null is its own
    // state, and it is the one that says the screen still owes an answer.
    render(
      <Settings
        {...PROPS}
        preferences={{ ...DEFAULT_PREFERENCES, reporter_type: null }}
      />,
    )

    expect(screen.getByRole('combobox', { name: /signed as/i })).toHaveValue('')
    expect(screen.getByRole('option', { name: /not set/i })).toBeInTheDocument()
  })

  it('lets a hiker correct what their reports say about them', async () => {
    // Editable here and not only at first contribution: someone who skipped
    // the screen, or who started section-hiking after a day hike, had no way
    // to change the one attribution a maintainer actually reads.
    const user = userEvent.setup()
    render(
      <Settings
        {...PROPS}
        preferences={{ ...DEFAULT_PREFERENCES, reporter_type: null }}
      />,
    )

    await user.selectOptions(
      screen.getByRole('combobox', { name: /signed as/i }),
      'section',
    )

    expect(PROPS.onChange).toHaveBeenCalledWith({ reporter_type: 'section' })
  })

  it('says a maintainer claim is still unverified', () => {
    render(
      <Settings
        {...PROPS}
        preferences={{ ...DEFAULT_PREFERENCES, reporter_type: 'maintainer' }}
      />,
    )

    expect(screen.getByText(/unverified/i)).toBeInTheDocument()
  })

  it('still says reading the map needs no account, even on the account row', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getByText(/never needs an account/i)).toBeInTheDocument()
  })

  it('shows when data last synced, and offers to sync now', async () => {
    const user = userEvent.setup()
    render(<Settings {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /^sync$/i }))

    expect(PROPS.onSync).toHaveBeenCalledTimes(1)
  })

  it('says the data has never synced rather than leaving it blank', () => {
    render(<Settings {...PROPS} lastSyncedAt={null} />)

    expect(screen.getByText(/never synced/i)).toBeInTheDocument()
  })

  it('offers export in both formats the wireframe names', async () => {
    const user = userEvent.setup()
    render(<Settings {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /GPX/i }))

    expect(PROPS.onExport).toHaveBeenCalledWith('gpx')
    expect(screen.getByRole('button', { name: /GeoJSON/i })).toBeInTheDocument()
  })

  it('credits the data sources, which the licences require', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getByText(/OpenStreetMap/i)).toBeInTheDocument()
  })

  it('exports GeoJSON as well as GPX', async () => {
    const user = userEvent.setup()
    render(<Settings {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /GeoJSON/i }))

    expect(PROPS.onExport).toHaveBeenCalledWith('geojson')
  })

  it('shows a reporter type it has no label for rather than a blank', () => {
    // The set of reporter types can grow server-side ahead of this build.
    render(
      <Settings
        {...PROPS}
        preferences={{
          ...DEFAULT_PREFERENCES,
          reporter_type: 'ridgerunner' as 'thru',
        }}
      />,
    )

    // Shown by its raw id rather than dropped: a select with no matching
    // option renders as its FIRST one, which would quietly re-sign every
    // future report as a thru-hiker.
    expect(screen.getByRole('combobox', { name: /signed as/i })).toHaveValue(
      'ridgerunner',
    )
  })
})

describe('the location switch (#312)', () => {
  // `location_permission_requested` was written in exactly one place - the
  // onboarding completion handler - and that step is skippable. So "Not now"
  // during setup disabled GPS in this app for the life of the install, with no
  // row anywhere to turn it back on and a header that went on saying "Looking
  // for GPS…" about it.

  it('offers a live switch, not a Later tag', () => {
    render(<Settings {...PROPS} />)

    const location = screen.getByRole('checkbox', { name: /use my location/i })

    expect(location).toBeEnabled()
  })

  it('reads as off for the hiker who skipped the onboarding step', () => {
    render(
      <Settings
        {...PROPS}
        preferences={{ ...DEFAULT_PREFERENCES, location_permission_requested: false }}
      />,
    )

    expect(screen.getByRole('checkbox', { name: /use my location/i })).not.toBeChecked()
  })

  it('turns location back on, which is the whole point of the row', async () => {
    const user = userEvent.setup()
    render(
      <Settings
        {...PROPS}
        preferences={{ ...DEFAULT_PREFERENCES, location_permission_requested: false }}
      />,
    )

    await user.click(screen.getByRole('checkbox', { name: /use my location/i }))

    expect(PROPS.onChange).toHaveBeenCalledWith({ location_permission_requested: true })
  })

  it('turns it off again, so the switch is a switch rather than a one-shot', async () => {
    const user = userEvent.setup()
    render(
      <Settings
        {...PROPS}
        preferences={{ ...DEFAULT_PREFERENCES, location_permission_requested: true }}
      />,
    )

    await user.click(screen.getByRole('checkbox', { name: /use my location/i }))

    expect(PROPS.onChange).toHaveBeenCalledWith({ location_permission_requested: false })
  })
})

// The full category list (#530). WIREFRAMES.md §2 has always put it here rather
// than in the legend, and the reason is one of the three consequences that issue
// lists: the legend's rows are per-viewport by design, so a category with no
// points in view has no row there and could not be turned back on.
describe('waypoints shown', () => {
  it('lists every hideable category', () => {
    renderSettings({ preferences: { ...DEFAULT_PREFERENCES, waypoint_types_shown: [] } })

    const group = within(screen.getByRole('group', { name: /waypoints shown/i }))
    expect(group.getAllByRole('checkbox').length).toBe(HIDEABLE_TYPES.length)
  })

  it('shows every category as on when the preference is empty', () => {
    // `[]` means all, which is what a fresh install has.
    renderSettings({ preferences: { ...DEFAULT_PREFERENCES, waypoint_types_shown: [] } })

    const group = within(screen.getByRole('group', { name: /waypoints shown/i }))
    for (const box of group.getAllByRole('checkbox')) expect(box).toBeChecked()
  })

  it('writes the preference when a category is turned off', async () => {
    const onChange = vi.fn()
    renderSettings({
      preferences: { ...DEFAULT_PREFERENCES, waypoint_types_shown: [] },
      onChange,
    })

    const group = within(screen.getByRole('group', { name: /waypoints shown/i }))
    await userEvent.click(group.getByRole('checkbox', { name: /privy/i }))

    // Through the same `onChange` path every other preference here uses, so it
    // persists and syncs rather than being the one control that forgets.
    const patch = onChange.mock.calls[0][0] as { waypoint_types_shown: string[] }
    expect(patch.waypoint_types_shown).not.toContain('privy')
    expect(patch.waypoint_types_shown).toContain('water')
  })

  it('offers no way to hide a safety layer', () => {
    // Absent rather than listed-and-disabled, which is how the rule is kept.
    renderSettings({ preferences: { ...DEFAULT_PREFERENCES, waypoint_types_shown: [] } })

    const group = within(screen.getByRole('group', { name: /waypoints shown/i }))
    expect(group.queryByRole('checkbox', { name: /closure/i })).not.toBeInTheDocument()
    expect(
      group.queryByRole('checkbox', { name: /serious warning/i }),
    ).not.toBeInTheDocument()
  })

  it('reflects a category that is already hidden', () => {
    renderSettings({
      preferences: {
        ...DEFAULT_PREFERENCES,
        waypoint_types_shown: HIDEABLE_TYPES.filter((type) => type !== 'privy'),
      },
    })

    const group = within(screen.getByRole('group', { name: /waypoints shown/i }))
    expect(group.getByRole('checkbox', { name: /privy/i })).not.toBeChecked()
    expect(group.getByRole('checkbox', { name: /water/i })).toBeChecked()
  })
})
