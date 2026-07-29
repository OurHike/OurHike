import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReportTypePicker } from './ReportTypePicker'

// WIREFRAMES.md §6. Five condition types in a grid, then a SEPARATE section
// for things about people, holding one full-width card rather than a sixth
// icon button - the wireframe is explicit that this is "deliberately not icon
// buttons", because reporting that someone threatened you should not look
// like reporting litter.
//
// "Say thanks to a maintainer" is NOT here. WIREFRAMES.md's own Known
// Deviations #2 flags it as an open product/data-model question - it is not a
// condition report, has no hazard location, and does not fit the Report
// model's type enum as written. Shipping a guess would bake in the wrong
// shape; a test asserts its absence so it stays an open question rather than
// quietly becoming a decision.

const PROPS = { onPick: vi.fn() }

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ReportTypePicker', () => {
  it('offers exactly the five condition types', () => {
    render(<ReportTypePicker {...PROPS} />)
    const grid = screen.getByRole('group', { name: /trail conditions/i })

    expect(within(grid).getAllByRole('button')).toHaveLength(5)
  })

  it.each([
    [/blow ?down/i, 'blowdown'],
    [/flooding/i, 'flooding'],
    [/trash/i, 'trash'],
    [/shelter/i, 'shelter_repair'],
    [/animals/i, 'animals'],
  ])('reports %s as the %s type', async (label, type) => {
    const user = userEvent.setup()
    render(<ReportTypePicker {...PROPS} />)

    await user.click(screen.getByRole('button', { name: label }))

    expect(PROPS.onPick).toHaveBeenCalledWith(type)
  })

  it('keeps the people section separate from the conditions grid', () => {
    render(<ReportTypePicker {...PROPS} />)

    expect(
      screen.getByRole('group', { name: /about people on the trail/i }),
    ).toBeInTheDocument()
  })

  it('offers the unsafe-behaviour card, mapped to the bad_hikers type', async () => {
    const user = userEvent.setup()
    render(<ReportTypePicker {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /something unsafe happened/i }))

    expect(PROPS.onPick).toHaveBeenCalledWith('bad_hikers')
  })

  it('does not offer "say thanks" - its data model is still an open question', () => {
    render(<ReportTypePicker {...PROPS} />)

    expect(screen.queryByText(/thanks/i)).toBe(null)
  })

  it('warns that the unsafe path is not an emergency service, before it is tapped', () => {
    render(<ReportTypePicker {...PROPS} />)

    expect(screen.getByText(/911/)).toHaveTextContent(/danger/i)
  })

  it('is honest that reports reach volunteers slowly, sometimes days later', () => {
    render(<ReportTypePicker {...PROPS} />)

    expect(screen.getByText(/days later/i)).toBeInTheDocument()
  })

  it('says an unsafe report stays private to moderators, never a public pin', () => {
    render(<ReportTypePicker {...PROPS} />)

    expect(screen.getByText(/never a public pin|private to/i)).toBeInTheDocument()
  })

  it('reassures that reading the map never needs an account', () => {
    render(<ReportTypePicker {...PROPS} />)

    expect(screen.getByText(/never needs an account/i)).toBeInTheDocument()
  })
})
