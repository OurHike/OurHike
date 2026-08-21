import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { ElevationRibbon } from './ElevationRibbon'
import { naismithTime } from '../lib/naismith'

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
})
