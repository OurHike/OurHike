import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MapDetailPicker } from './MapDetailPicker'
import { PREFERENCE_KEYS } from '../lib/userPreferences'

afterEach(cleanup)

const group = () => within(screen.getByRole('group', { name: /map detail/i }))

describe('MapDetailPicker', () => {
  it('offers all three levels as one radio group', () => {
    render(<MapDetailPicker value="standard" onChange={() => {}} />)

    const values = group()
      .getAllByRole('radio')
      .map((radio) => (radio as HTMLInputElement).value)

    expect(values.sort()).toEqual(['full', 'minimal', 'standard'])
  })

  it('groups them on the canonical field name', () => {
    // `layer_detail_level` predates this control by some months - the key
    // shipped in the schema unwired (backend/app/schemas/preferences.py
    // requires it), and the control has to write the key that already syncs.
    render(<MapDetailPicker value="standard" onChange={() => {}} />)

    expect(PREFERENCE_KEYS).toContain('layer_detail_level')
    for (const radio of group().getAllByRole('radio')) {
      expect(radio).toHaveAttribute('name', 'layer_detail_level')
    }
  })

  it('shows the current choice as the checked one', () => {
    render(<MapDetailPicker value="minimal" onChange={() => {}} />)

    const checked = group()
      .getAllByRole('radio')
      .find((radio) => (radio as HTMLInputElement).checked)

    expect((checked as HTMLInputElement).value).toBe('minimal')
  })

  it('reports a change as the preference value, not as a label', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<MapDetailPicker value="standard" onChange={onChange} />)

    await user.click(screen.getByRole('radio', { name: /minimal/i }))

    expect(onChange).toHaveBeenCalledWith('minimal')
  })

  it('says what minimal KEEPS, so less detail does not read as less map', () => {
    // The level exists for a hiker overwhelmed by ink; a description that
    // only listed losses would scare off exactly that hiker. mapDetail.ts's
    // matrix keeps index contours and side paths, so the words have to.
    render(<MapDetailPicker value="minimal" onChange={() => {}} />)

    expect(screen.getByText(/index contours/i)).toBeInTheDocument()
    expect(screen.getByText(/side paths/i)).toBeInTheDocument()
  })
})
