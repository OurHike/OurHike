import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemePicker } from './ThemePicker'
import { PREFERENCE_KEYS } from '../lib/userPreferences'

afterEach(cleanup)

const group = () => within(screen.getByRole('group', { name: /theme/i }))

describe('ThemePicker', () => {
  it('offers all three choices as one radio group', () => {
    render(<ThemePicker value="auto" onChange={() => {}} />)

    const values = group()
      .getAllByRole('radio')
      .map((radio) => (radio as HTMLInputElement).value)

    expect(values.sort()).toEqual(['auto', 'dark', 'light'])
  })

  it('groups them on the canonical field name', () => {
    // `theme` is the key in UserPreferences and in the backend's schema
    // (backend/app/schemas/preferences.py). A name invented here would be a
    // 422 the moment somebody signs in.
    render(<ThemePicker value="auto" onChange={() => {}} />)

    expect(PREFERENCE_KEYS).toContain('theme')
    for (const radio of group().getAllByRole('radio')) {
      expect(radio).toHaveAttribute('name', 'theme')
    }
  })

  it('shows the current choice as the checked one', () => {
    render(<ThemePicker value="dark" onChange={() => {}} />)

    const checked = group()
      .getAllByRole('radio')
      .find((radio) => (radio as HTMLInputElement).checked)

    expect((checked as HTMLInputElement).value).toBe('dark')
  })

  it('reports a change as the preference value, not as a label', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<ThemePicker value="auto" onChange={onChange} />)

    await user.click(screen.getByRole('radio', { name: /dark/i }))

    expect(onChange).toHaveBeenCalledWith('dark')
  })

  it('says plainly that dark is not the answer to glare', () => {
    // features/UX_CUSTOMIZATION.md makes this an explicit non-goal, and the
    // reason it is worth saying in the UI rather than only in a doc is that
    // the mistake is the intuitive one: somebody squinting at a screen in full
    // sun reaches for the darker option first. Asserted because the sentence
    // is the feature here, not decoration around it.
    render(<ThemePicker value="dark" onChange={() => {}} />)

    expect(screen.getByText(/glare/i)).toBeInTheDocument()
    expect(screen.getByText(/night vision/i)).toBeInTheDocument()
  })
})
