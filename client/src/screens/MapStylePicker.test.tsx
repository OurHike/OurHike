import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MapStylePicker } from './MapStylePicker'
import { MAP_STYLE_VALUES, PREFERENCE_KEYS } from '../lib/userPreferences'

afterEach(cleanup)

const group = () => within(screen.getByRole('group', { name: /map style/i }))

describe('MapStylePicker', () => {
  it('offers exactly the styles the build can draw, as one radio group', () => {
    // The option list and MAP_STYLE_VALUES gate the same set: a style offered
    // here that the palette lookup does not know would be a control writing a
    // value nothing can render.
    render(<MapStylePicker value="field" onChange={() => {}} />)

    const values = group()
      .getAllByRole('radio')
      .map((radio) => (radio as HTMLInputElement).value)

    expect(values.sort()).toEqual([...MAP_STYLE_VALUES].sort())
  })

  it('groups them on the canonical field name', () => {
    // `map_style` is the key in UserPreferences and in the backend's schema
    // (backend/app/schemas/preferences.py). A name invented here would be a
    // 422 the moment somebody signs in.
    render(<MapStylePicker value="field" onChange={() => {}} />)

    expect(PREFERENCE_KEYS).toContain('map_style')
    for (const radio of group().getAllByRole('radio')) {
      expect(radio).toHaveAttribute('name', 'map_style')
    }
  })

  it('shows the current choice as the checked one', () => {
    render(<MapStylePicker value="night_hike" onChange={() => {}} />)

    const checked = group()
      .getAllByRole('radio')
      .find((radio) => (radio as HTMLInputElement).checked)

    expect((checked as HTMLInputElement).value).toBe('night_hike')
  })

  it('reports a change as the preference value, not as a label', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<MapStylePicker value="field" onChange={onChange} />)

    await user.click(screen.getByRole('radio', { name: /night hike/i }))

    expect(onChange).toHaveBeenCalledWith('night_hike')
  })

  it('tells a hiker on Field what happens after dark', () => {
    // The auto-dark switch is otherwise invisible until sunset performs it.
    // The sentence is the feature, so the sentence is asserted.
    render(<MapStylePicker value="field" onChange={() => {}} />)

    expect(screen.getByText(/after dark/i)).toBeInTheDocument()
  })

  it('says what choosing Night hike outright is for', () => {
    render(<MapStylePicker value="night_hike" onChange={() => {}} />)

    expect(screen.getByText(/night vision/i)).toBeInTheDocument()
  })
})
