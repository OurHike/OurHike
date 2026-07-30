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
// "Say thanks to a maintainer" now lives in that same people section, decided
// 2026-07-29 (features/SAYING_THANKS.md, resolving Known Deviations #2): a
// thanks is a comment about a specific place, so it is the seventh report
// type. It is deliberately NOT a sixth condition tile - it is not a trail
// condition, and the grid stays at five.

const PROPS = { onPick: vi.fn() }

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ReportTypePicker', () => {
  it('offers exactly the six condition types', () => {
    render(<ReportTypePicker {...PROPS} />)
    const grid = screen.getByRole('group', { name: /trail conditions/i })

    expect(within(grid).getAllByRole('button')).toHaveLength(6)
  })

  it.each([
    [/blow ?down/i, 'blowdown'],
    [/flooding/i, 'flooding'],
    [/trash/i, 'trash'],
    [/shelter/i, 'shelter_repair'],
    [/animals/i, 'animals'],
    [/invasive/i, 'invasive_species'],
  ])('reports %s as the %s type', async (label, type) => {
    const user = userEvent.setup()
    render(<ReportTypePicker {...PROPS} />)

    await user.click(screen.getByRole('button', { name: label }))

    expect(PROPS.onPick).toHaveBeenCalledWith(type)
  })

  it('distinguishes invasive species from animals at the point of choice', async () => {
    // The two genuinely overlap - a feral hog is both - so the difference has
    // to be legible where someone is choosing, not in a data dictionary
    // nobody reads. `animals` is an encounter that worried you;
    // `invasive_species` is something spreading where it should not be.
    render(<ReportTypePicker {...PROPS} />)
    const grid = screen.getByRole('group', { name: /trail conditions/i })

    expect(within(grid).getByRole('button', { name: /invasive/i })).toHaveAccessibleName(
      /Plants or pests that shouldn't be here/i,
    )
    expect(within(grid).getByRole('button', { name: /animals/i })).toHaveAccessibleName(
      /Sightings, food raids, anything aggressive/i,
    )
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

  it('offers the thanks card, mapped to the thanks type', async () => {
    const user = userEvent.setup()
    render(<ReportTypePicker {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /say thanks/i }))

    expect(PROPS.onPick).toHaveBeenCalledWith('thanks')
  })

  it('keeps thanks out of the conditions grid - it is not a trail condition', () => {
    render(<ReportTypePicker {...PROPS} />)
    const grid = screen.getByRole('group', { name: /trail conditions/i })

    expect(within(grid).queryByText(/thanks/i)).toBe(null)
  })

  it('puts thanks in the people section, alongside the unsafe card', () => {
    render(<ReportTypePicker {...PROPS} />)
    const people = screen.getByRole('group', { name: /about people on the trail/i })

    expect(
      within(people).getByRole('button', { name: /say thanks/i }),
    ).toBeInTheDocument()
  })

  it('does not offer a rating or score anywhere - thanks is not a review', () => {
    render(<ReportTypePicker {...PROPS} />)

    expect(screen.queryByText(/rate|rating|stars|★/i)).toBe(null)
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
