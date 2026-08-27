import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { ElevationRibbon } from './ElevationRibbon'
import { naismithTime } from '../lib/naismith'
import { ribbonGeometry } from '../lib/ribbonGeometry'

// Spied rather than replaced: every test below still exercises the real
// geometry; the spy exists so the memo test can count how often it runs.
vi.mock('../lib/ribbonGeometry', { spy: true })

// WIREFRAMES.md §1.3. The geometry values are specified exactly - viewBox
// "0 0 100 40" with preserveAspectRatio="none" so the profile stretches to
// whatever width the phone has, 54px tall, 36px left inset for the lane
// labels below it - and are asserted here because they are what keep the
// ribbon aligned with the waypoint lanes underneath.
//
// The callout ("+640 ft · 2.6 mi · ≈1h 10m") must derive its estimate from
// lib/naismith.ts rather than carrying its own copy of the arithmetic, and
// must never read as an arrival clock.

const SAMPLES = [
  { mile: 1400, elevationFt: 1200 },
  { mile: 1402, elevationFt: 1500 },
  { mile: 1404, elevationFt: 1840 },
  { mile: 1406, elevationFt: 1600 },
  { mile: 1408, elevationFt: 2100 },
  { mile: 1410, elevationFt: 980 },
]

const PROPS = {
  samples: SAMPLES,
  currentMile: 1405,
  upcomingClimb: { startMile: 1406, endMile: 1408.6, ascentFt: 640 },
}

afterEach(() => {
  cleanup()
})

describe('ElevationRibbon', () => {
  it('uses the exact SVG geometry the wireframe specifies', () => {
    render(<ElevationRibbon {...PROPS} />)
    const svg = screen.getByRole('img', { name: /elevation profile/i })

    expect(svg).toHaveAttribute('viewBox', '0 0 100 40')
    expect(svg).toHaveAttribute('preserveAspectRatio', 'none')
  })

  it('labels the lowest and highest elevation in the window', () => {
    render(<ElevationRibbon {...PROPS} />)

    expect(screen.getByText(/980 ft/)).toBeInTheDocument()
    expect(screen.getByText(/2,100 ft/)).toBeInTheDocument()
  })

  it('marks where you are as a percentage along the window', () => {
    render(<ElevationRibbon {...PROPS} />)

    // 1405 of 1400-1410 is halfway.
    expect(screen.getByTestId('you-are-here')).toHaveAttribute('x1', '50')
  })

  it('shades the area under the profile rather than drawing a bare line', () => {
    render(<ElevationRibbon {...PROPS} />)

    // A filled area closes back along the baseline; a bare polyline does not.
    expect(screen.getByTestId('profile-area').getAttribute('d')).toMatch(/Z$/)
  })

  it('stands for the domain it is given rather than for its own samples', () => {
    // The lanes underneath are positioned against the domain, so this is what
    // keeps a pin under the ground it names. The samples cover 1400-1410; the
    // domain is 1400-1420, so they occupy the left half rather than being
    // stretched over ten miles nothing measured.
    render(<ElevationRibbon {...PROPS} domain={{ startMile: 1400, endMile: 1420 }} />)

    // 1405 of 1400-1420 is a quarter along, where it was halfway without one.
    expect(screen.getByTestId('you-are-here')).toHaveAttribute('x1', '25')
    // And the shading stops where the samples do rather than filling out to
    // the edge, which would be ground nobody measured.
    expect(screen.getByTestId('profile-area').getAttribute('d')).toMatch(
      /L50\.00,40 L0\.00,40 Z$/,
    )
  })

  it('highlights the upcoming climb', () => {
    render(<ElevationRibbon {...PROPS} />)

    expect(screen.getByTestId('upcoming-climb')).toBeInTheDocument()
  })

  it('states the climb ahead as ascent, distance and an estimate', () => {
    render(<ElevationRibbon {...PROPS} />)

    expect(screen.getByText(/\+640 ft · 2\.6 mi · ≈1h 10m/)).toBeInTheDocument()
  })

  // #619. All three labels, in one component, from one preference - a ribbon
  // with its high mark in metres and its callout in feet would be worse than
  // either alone.
  it('reads in metres and kilometres for a hiker who chose them', () => {
    render(<ElevationRibbon {...PROPS} units="metric" />)

    expect(screen.getByText(/299 m/)).toBeInTheDocument()
    expect(screen.getByText(/640 m/)).toBeInTheDocument()
    expect(screen.getByText(/\+195 m · 4\.2 km · ≈1h 10m/)).toBeInTheDocument()
  })

  it('keeps the estimate in the units time is measured in, whatever the hiker chose', () => {
    // Naismith's arithmetic is metric underneath and its OUTPUT is a duration,
    // which has no unit system to belong to. The one part of the callout that
    // must not move when the preference does.
    render(<ElevationRibbon {...PROPS} units="metric" />)

    expect(screen.getByTestId('climb-callout')).toHaveTextContent(
      naismithTime({ distanceMi: 2.6, ascentFt: 640 }),
    )
  })

  it('takes its estimate from lib/naismith rather than keeping a second copy of the maths', () => {
    render(<ElevationRibbon {...PROPS} />)
    const expected = naismithTime({ distanceMi: 2.6, ascentFt: 640 })

    expect(screen.getByText(new RegExp(expected.replace(/[≈]/, '≈')))).toBeInTheDocument()
  })

  it('never presents the estimate as a clock time - it is a duration, not an arrival', () => {
    render(<ElevationRibbon {...PROPS} />)
    const callout = screen.getByTestId('climb-callout').textContent ?? ''

    // No "3:45", no "PM" - WIREFRAMES.md is explicit that an arrival time
    // would be a promise this rule cannot keep.
    expect(callout).not.toMatch(/\d{1,2}:\d{2}/)
    expect(callout).not.toMatch(/[ap]\.?m\.?/i)
  })

  it('always carries the ≈ prefix, so the estimate never reads as precise', () => {
    render(<ElevationRibbon {...PROPS} />)

    expect(screen.getByTestId('climb-callout')).toHaveTextContent('≈')
  })

  it('omits the callout entirely when there is no climb ahead', () => {
    render(<ElevationRibbon {...PROPS} upcomingClimb={undefined} />)

    expect(screen.queryByTestId('climb-callout')).not.toBeInTheDocument()
    expect(screen.queryByTestId('upcoming-climb')).not.toBeInTheDocument()
  })

  it('renders without crashing when the profile is flat', () => {
    // A flat window makes max === min; naive scaling would divide by zero and
    // emit NaN into the path, which renders as nothing at all.
    render(
      <ElevationRibbon
        samples={[
          { mile: 1400, elevationFt: 1000 },
          { mile: 1410, elevationFt: 1000 },
        ]}
        currentMile={1405}
      />,
    )

    expect(screen.getByTestId('profile-area').getAttribute('d')).not.toMatch(/NaN/)
  })

  it('renders without a profile at all when there are no samples yet', () => {
    // Before elevation_profile.json has been downloaded. An empty ribbon is
    // fine; a crash on samples[0] is not.
    render(<ElevationRibbon samples={[]} currentMile={0} />)

    expect(screen.getByTestId('profile-area').getAttribute('d')).not.toMatch(/NaN/)
  })

  it('does not divide by zero when every sample sits at the same mile', () => {
    // A degenerate window - one sample repeated, or a profile clipped to a
    // single point - would otherwise put NaN straight into the SVG path and
    // render nothing, silently.
    render(
      <ElevationRibbon
        samples={[
          { mile: 1400, elevationFt: 1000 },
          { mile: 1400, elevationFt: 1200 },
        ]}
        currentMile={1400}
      />,
    )

    expect(screen.getByTestId('profile-area').getAttribute('d')).not.toMatch(/NaN/)
  })

  // The planning ribbon (#910). Same geometry, same shading, same labels -
  // what changes is the three things that make a claim about a hiker.

  it('draws no you-are-here rule when nothing knows where the hiker is', () => {
    render(<ElevationRibbon samples={SAMPLES} currentMile={null} />)

    expect(screen.queryByTestId('you-are-here')).not.toBeInTheDocument()
  })

  it('draws no rule for a fix that is not on the stretch being drawn', () => {
    // Clamped to an edge, the rule would read as "you are at the start of
    // this stretch" - a confident answer about somebody's position, and a
    // wrong one. A hiker in Virginia planning the Whites is the normal case.
    render(<ElevationRibbon samples={SAMPLES} currentMile={700} />)

    expect(screen.queryByTestId('you-are-here')).not.toBeInTheDocument()
  })

  it('still draws the rule for a fix that IS on the stretch', () => {
    render(
      <ElevationRibbon samples={SAMPLES} currentMile={1405} subject="planned-stretch" />,
    )

    expect(screen.getByTestId('you-are-here')).toHaveAttribute('x1', '50')
  })

  it('stops calling the profile "ahead" when it is a planned stretch', () => {
    render(
      <ElevationRibbon samples={SAMPLES} currentMile={null} subject="planned-stretch" />,
    )

    expect(
      screen.getByRole('img', { name: /stretch being planned/i }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: /ahead/i })).not.toBeInTheDocument()
  })

  it('calls a followed walk "your whole walk today" and not "ahead"', () => {
    // #1045. "Ahead" is the strongest claim these five labels make and it is
    // about the A.T.; a screen reader saying it over a Harriman loop has told
    // a hiker something false about where they are going.
    render(<ElevationRibbon samples={SAMPLES} currentMile={null} subject="todays-walk" />)

    expect(screen.getByRole('img', { name: /whole walk today/i })).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: /ahead/i })).not.toBeInTheDocument()
  })

  it('breaks the line at ground it has no shape for, rather than sloping across it', () => {
    // #1045, #983: a day hike built from two stretches has ground between
    // them OurHike will not route - a road walk, most often. A line drawn
    // across it would be a picture of terrain nobody measured.
    render(
      <ElevationRibbon
        samples={[
          { mile: 0, elevationFt: 1000 },
          { mile: 1, elevationFt: 1400 },
          { mile: 1, elevationFt: 900, partStart: true },
          { mile: 2, elevationFt: 1100 },
        ]}
        currentMile={null}
        subject="todays-walk"
      />,
    )

    // Two subpaths, so nothing is stroked between the two `M`s.
    const line = screen.getByTestId('profile-area').getAttribute('d') ?? ''
    expect(line.match(/M/g)).toHaveLength(2)
    // And two closed areas, so the shading does not fill the gap either.
    expect(line.match(/Z/g)).toHaveLength(2)
  })

  it('draws one unbroken path when nothing is marked, exactly as it always did', () => {
    // Every ribbon that existed before #1045 carries no marker at all, and
    // this is what says the marker costs them nothing.
    render(<ElevationRibbon {...PROPS} />)

    const line = screen.getByTestId('profile-area').getAttribute('d') ?? ''
    expect(line.match(/M/g)).toHaveLength(1)
    expect(line.match(/Z/g)).toHaveLength(1)
  })

  it('draws the framing buttons the screen hands it, and none of its own', () => {
    const zoom = vi.fn()
    render(
      <ElevationRibbon
        samples={SAMPLES}
        currentMile={null}
        controls={[{ label: 'Whole trail', onClick: zoom }]}
      />,
    )

    expect(
      screen.queryByRole('button', { name: 'Zoom to stretch' }),
    ).not.toBeInTheDocument()
    screen.getByRole('button', { name: 'Whole trail' }).click()
    expect(zoom).toHaveBeenCalledOnce()
  })

  it('costs the map no row at all when there is nothing to frame', () => {
    // The row is real layout, not an overlay, so an empty one would take ~44px
    // of map height to say nothing.
    const { container } = render(<ElevationRibbon samples={SAMPLES} currentMile={null} />)

    expect(container.querySelector('.elevation-ribbon-controls')).toBeNull()

    cleanup()
    const empty = render(
      <ElevationRibbon samples={SAMPLES} currentMile={null} controls={[]} />,
    )
    expect(empty.container.querySelector('.elevation-ribbon-controls')).toBeNull()
  })

  it('draws the profile and the labels with no fix, exactly as with one', () => {
    // The picture is the whole point of the planning ribbon. Losing the rule
    // must not cost the shape or the two elevation labels with it.
    render(<ElevationRibbon samples={SAMPLES} currentMile={null} />)

    expect(screen.getByTestId('profile-area').getAttribute('d')).not.toMatch(/NaN/)
    expect(screen.getByText(/980 ft/)).toBeInTheDocument()
    expect(screen.getByText(/2,100 ft/)).toBeInTheDocument()
  })

  it('rebuilds the path only when the samples or the domain change (#1111)', () => {
    // The shell re-renders once per GPS callback while a phone sits still
    // (#1100), and reaches here with the samples' identity held now that the
    // upstream memos key on the mile. This is the other half of that change:
    // a re-render with the same ground must not rebuild the ~640-point path.
    const { rerender } = render(<ElevationRibbon samples={SAMPLES} currentMile={1405} />)
    const built = () => vi.mocked(ribbonGeometry).mock.calls.length
    const before = built()

    rerender(<ElevationRibbon samples={SAMPLES} currentMile={1405} />)
    expect(built()).toBe(before)

    // The rule and the callout may move without the drawn ground changing -
    // the mile is not part of the geometry's key.
    rerender(<ElevationRibbon samples={SAMPLES} currentMile={1406} />)
    expect(built()).toBe(before)

    // A new samples array is a new picture, whatever it holds.
    rerender(<ElevationRibbon samples={[...SAMPLES]} currentMile={1406} />)
    expect(built()).toBe(before + 1)
  })
})
