import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { UnitPicker } from './UnitPicker'
import { PREFERENCE_KEYS } from '../lib/userPreferences'

afterEach(cleanup)

const group = () => within(screen.getByRole('group', { name: /units/i }))

describe('UnitPicker', () => {
  it('offers both systems as one radio group', () => {
    render(<UnitPicker value="imperial" onChange={() => {}} />)

    const values = group()
      .getAllByRole('radio')
      .map((radio) => (radio as HTMLInputElement).value)

    expect(values.sort()).toEqual(['imperial', 'metric'])
  })

  it('groups them on the canonical field name', () => {
    // `unit_system` is the key in UserPreferences and in the backend's schema
    // (backend/app/schemas/preferences.py). A name invented here would be a
    // 422 the moment somebody signs in.
    render(<UnitPicker value="imperial" onChange={() => {}} />)

    expect(PREFERENCE_KEYS).toContain('unit_system')
    for (const radio of group().getAllByRole('radio')) {
      expect(radio).toHaveAttribute('name', 'unit_system')
    }
  })

  it('shows the current choice as the checked one', () => {
    render(<UnitPicker value="metric" onChange={() => {}} />)

    const checked = group()
      .getAllByRole('radio')
      .find((radio) => (radio as HTMLInputElement).checked)

    expect((checked as HTMLInputElement).value).toBe('metric')
  })

  it('reports a change as the preference value, not as a label', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<UnitPicker value="imperial" onChange={onChange} />)

    await user.click(screen.getByRole('radio', { name: /metres/i }))

    expect(onChange).toHaveBeenCalledWith('metric')
  })

  it('is labelled by the unit a hiker reads, not by the system it belongs to', () => {
    // "Imperial" and "Metric" are the wire values and the wrong words on a
    // screen: a hiker asks "can I get this in metres?", and the segment they
    // are looking for should be spelled the way they asked.
    render(<UnitPicker value="imperial" onChange={() => {}} />)

    expect(screen.getByRole('radio', { name: /feet/i })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /metres/i })).toBeInTheDocument()
  })

  it('says that the choice carries distances too, before it is made', () => {
    // The surprise this control can spend four words preventing: somebody
    // picking "Metres" is also picking kilometres, and finding that out
    // afterwards on the closure banner is worse than reading it here.
    render(<UnitPicker value="imperial" onChange={() => {}} />)

    expect(screen.getByRole('radio', { name: /and miles/i })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /and kilometres/i })).toBeInTheDocument()
  })

  it('states the mile-marker exception under either choice', () => {
    // The one thing that does not convert (lib/units.ts). A metric hiker whose
    // ribbon reads in metres while the milepost under it still reads
    // `mi 1,407.2` is owed that sentence here rather than left to conclude the
    // app is half-finished - and an imperial hiker deciding whether to switch
    // is owed it before they do.
    for (const value of ['imperial', 'metric'] as const) {
      cleanup()
      render(<UnitPicker value={value} onChange={() => {}} />)
      expect(screen.getByText(/mile markers stay in miles/i)).toBeInTheDocument()
    }
  })
})
