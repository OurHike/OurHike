import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { PaceSettings } from './PaceSettings'
import {
  DESCENT_STEP_MINUTES,
  FLAT_PACE_STEP_MPH,
  MAX_DESCENT_MINUTES_PER_1000M,
  MIN_DESCENT_MINUTES_PER_1000M,
  MAX_FLAT_PACE_MPH,
  MIN_FLAT_PACE_MPH,
  MAX_ASCENT_METERS_PER_HOUR,
  MIN_ASCENT_METERS_PER_HOUR,
  STANDARD_PACE,
  type PaceProfile,
} from '../lib/pace'

const SLOWER: PaceProfile = {
  flatPaceMph: 2.6,
  ascentMetersPerHour: 480,
  descentMinutesPer1000m: 0,
}

afterEach(cleanup)

describe('the pace controls', () => {
  it('starts at the standard, and says so under each control', () => {
    render(<PaceSettings pace={STANDARD_PACE} units="imperial" onChange={vi.fn()} />)
    expect(screen.getByText('Standard is 3.1 mph')).toBeInTheDocument()
    expect(screen.getByText('Standard is +1h / 1,969 ft')).toBeInTheDocument()
  })

  it('reports a new flat pace to the caller', () => {
    const onChange = vi.fn()
    render(<PaceSettings pace={STANDARD_PACE} units="imperial" onChange={onChange} />)
    fireEvent.change(screen.getByLabelText('Flat pace'), { target: { value: '2.6' } })
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ flatPaceMph: 2.6 }))
  })

  it('makes dragging the climbing control RIGHT mean a steeper penalty', () => {
    // The underlying number runs the other way - fewer metres per hour is
    // harder - so left-to-right has to be inverted or the control reads
    // backwards. This is the assertion that catches it being un-inverted.
    const onChange = vi.fn()
    render(<PaceSettings pace={STANDARD_PACE} units="imperial" onChange={onChange} />)
    const climb = screen.getByLabelText('Climbing penalty')

    fireEvent.change(climb, { target: { value: String(MAX_ASCENT_METERS_PER_HOUR) } })
    const dragged = onChange.mock.calls[0][0] as PaceProfile
    expect(dragged.ascentMetersPerHour).toBe(MIN_ASCENT_METERS_PER_HOUR)
    expect(dragged.ascentMetersPerHour).toBeLessThan(STANDARD_PACE.ascentMetersPerHour)
  })
})

/**
 * The preview is the control: nobody has a feel for "an hour per 480 metres",
 * and both sliders are only legible through what a real walk now reads.
 */
describe('the flat pace slider (#888)', () => {
  it('offers 1 to 4 mph in tenths', () => {
    render(<PaceSettings pace={STANDARD_PACE} units="imperial" onChange={vi.fn()} />)
    const flat = screen.getByLabelText('Flat pace')
    expect(flat).toHaveAttribute('min', String(MIN_FLAT_PACE_MPH))
    expect(flat).toHaveAttribute('max', String(MAX_FLAT_PACE_MPH))
    expect(flat).toHaveAttribute('step', String(FLAT_PACE_STEP_MPH))
  })

  it('lets a hiker say they are faster than standard', () => {
    // The decision. A hiker who genuinely moves at 4 mph should not be told a
    // number the app knows is wrong for them.
    const onChange = vi.fn()
    render(<PaceSettings pace={STANDARD_PACE} units="imperial" onChange={onChange} />)
    fireEvent.change(screen.getByLabelText('Flat pace'), { target: { value: '4' } })
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ flatPaceMph: 4 }))
  })

  it('marks a faster-than-standard estimate rather than clamping it', () => {
    // The safeguard is the baseline line, not a floor on the control. A hiker
    // reading a shorter time can always see the standard one beside it.
    const faster: PaceProfile = { ...STANDARD_PACE, flatPaceMph: 4 }
    render(<PaceSettings pace={faster} units="imperial" onChange={vi.fn()} />)
    expect(screen.getByText(/was ≈2h 10m · 0\.\d× standard/)).toBeInTheDocument()
  })

  it('offers Reset at the nearest stop, which is not the standard', () => {
    // 3.1069 mph is not a multiple of 0.1, so no stop on this slider is the
    // standard - 3.1 is the closest and is still not it. Reset is the only way
    // back to exactly the rule.
    //
    // 3.1 also prints the SAME estimate as the standard, so this is the case
    // where the baseline line stays silent and Reset does not: they answer
    // different questions.
    render(
      <PaceSettings
        pace={{ ...STANDARD_PACE, flatPaceMph: 3.1 }}
        units="imperial"
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: 'Reset to standard' })).toBeInTheDocument()
  })
})

describe('the live preview', () => {
  it('shows the standard estimate, and no baseline, at the standard pace', () => {
    render(<PaceSettings pace={STANDARD_PACE} units="imperial" onChange={vi.fn()} />)
    expect(screen.getByText('≈2h 10m')).toBeInTheDocument()
    expect(screen.queryByText(/× standard/)).not.toBeInTheDocument()
  })

  it('shows the adjusted estimate and what it was adjusted from', () => {
    render(<PaceSettings pace={SLOWER} units="imperial" onChange={vi.fn()} />)
    // 4.0 mi at 2.6 mph is 92.3 min; 1,740 ft over 480 m/h is 66.3 more.
    // 158.6 rounds to ≈2h 40m, against the standard's 130.3 -> 1.2×.
    expect(screen.getByText('≈2h 40m')).toBeInTheDocument()
    expect(screen.getByText(/^was ≈2h 10m · 1\.2× standard$/)).toBeInTheDocument()
  })

  it('describes the walk it is previewing, so the number means something', () => {
    render(<PaceSettings pace={SLOWER} units="imperial" onChange={vi.fn()} />)
    expect(
      screen.getByText(/for a 4\.0 mi walk with 1,740 ft up and 1,740 ft down/),
    ).toBeInTheDocument()
  })
})

describe('units', () => {
  it('shows a metric hiker km/h and metres', () => {
    // A pace is a speed, so it converts like every other distance in the app.
    render(<PaceSettings pace={STANDARD_PACE} units="metric" onChange={vi.fn()} />)
    expect(screen.getByText('Standard is 5.0 km/h')).toBeInTheDocument()
    expect(screen.getByText('Standard is +1h / 600 m')).toBeInTheDocument()
  })

  it('shows whole feet, through the same formatter as every other height', () => {
    // formatElevation's own rule: whole units in both systems, because "a
    // metre is close enough to three feet that the decimal a conversion
    // produces is noise".
    render(<PaceSettings pace={SLOWER} units="imperial" onChange={vi.fn()} />)
    expect(screen.getByText('+1h / 1,575 ft')).toBeInTheDocument()
  })

  it('converts the walk the preview describes, not just the controls', () => {
    // This line was hardcoded imperial, so a metric hiker read "4.0 mi with
    // 1,740 ft of climb" under a preview in km/h. The unit invariant test
    // caught it; this pins it.
    render(<PaceSettings pace={STANDARD_PACE} units="metric" onChange={vi.fn()} />)
    expect(
      screen.getByText(/for a 6\.4 km walk with 530 m up and 530 m down/),
    ).toBeInTheDocument()
  })
})

/**
 * The third control (#900), and the one direction it has.
 *
 * The maintainer reversed PERSONALIZED_PACE.md's lean to offer it at all. What
 * did NOT reverse is CLAUDE.md's no-descent-credit rule, so it only adds time.
 */
describe('the descent control', () => {
  it('starts at none, which is the standard', () => {
    render(<PaceSettings pace={STANDARD_PACE} units="imperial" onChange={vi.fn()} />)
    expect(screen.getByText('None')).toBeInTheDocument()
  })

  it('runs from none to an hour per 1,000 m in five-minute steps', () => {
    render(<PaceSettings pace={STANDARD_PACE} units="imperial" onChange={vi.fn()} />)
    const descent = screen.getByLabelText('Descent penalty')
    expect(descent).toHaveAttribute('min', String(MIN_DESCENT_MINUTES_PER_1000M))
    expect(descent).toHaveAttribute('max', String(MAX_DESCENT_MINUTES_PER_1000M))
    expect(descent).toHaveAttribute('step', String(DESCENT_STEP_MINUTES))
  })

  it('is NOT inverted, so dragging right is harder', () => {
    // The climbing control above is inverted because its number runs backwards.
    // This one does not, and a reader moving between them should not have to
    // guess which is which.
    const onChange = vi.fn()
    render(<PaceSettings pace={STANDARD_PACE} units="imperial" onChange={onChange} />)
    fireEvent.change(screen.getByLabelText('Descent penalty'), {
      target: { value: '30' },
    })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ descentMinutesPer1000m: 30 }),
    )
  })

  it('says out loud that it can only add time', () => {
    // A hiker who is genuinely quick downhill will look for the other
    // direction. The screen should tell them it is not there rather than let
    // them hunt for it.
    render(<PaceSettings pace={STANDARD_PACE} units="imperial" onChange={vi.fn()} />)
    expect(screen.getByText(/can only add time, never subtract it/)).toBeInTheDocument()
  })

  it("reads in the hiker's own units", () => {
    const knees: PaceProfile = { ...STANDARD_PACE, descentMinutesPer1000m: 30 }
    render(<PaceSettings pace={knees} units="metric" onChange={vi.fn()} />)
    expect(screen.getByText('+30 min / 1,000 m')).toBeInTheDocument()
  })
})

describe('resetting', () => {
  it('offers nothing to undo at the standard pace', () => {
    render(<PaceSettings pace={STANDARD_PACE} units="imperial" onChange={vi.fn()} />)
    expect(
      screen.queryByRole('button', { name: 'Reset to standard' }),
    ).not.toBeInTheDocument()
  })

  it('puts every estimate back on the rule', () => {
    const onChange = vi.fn()
    render(<PaceSettings pace={SLOWER} units="imperial" onChange={onChange} />)
    screen.getByRole('button', { name: 'Reset to standard' }).click()
    expect(onChange).toHaveBeenCalledWith(STANDARD_PACE)
  })
})

describe('what it promises about the data', () => {
  it('says the profile stays on the phone', () => {
    // PERSONALIZED_PACE.md §4 keeps a pace profile off the wire even once an
    // account exists. A screen that collects it should say so where it is
    // collected, not only in a policy.
    render(<PaceSettings pace={STANDARD_PACE} units="imperial" onChange={vi.fn()} />)
    expect(screen.getByText(/never sent anywhere/)).toBeInTheDocument()
  })
})
