import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReportForm } from './ReportForm'

// WIREFRAMES.md §6's report form: note, optional photo, location, "signed as
// <trail name> · <reporter type>", and the report's real timestamp - the
// moment of writing, not of sending.
//
// That last one is the load-bearing part and the reason this component takes
// its authoring time at MOUNT rather than at submit. Someone can start a
// report, walk on, and finish it twenty minutes later; the time that matters
// is when they saw the thing, and for a queued offline report the send may be
// days away. The matching server field is `authored_at` (see the reports API).

const PROPS = {
  type: 'blowdown' as const,
  trailName: 'Switchback',
  reporterType: 'thru' as const,
  location: { lat: 35.6, lon: -83.5, mile: 1043.2 },
  onSubmit: vi.fn(),
  onCancel: vi.fn(),
  now: new Date('2026-07-29T12:00:00Z'),
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('ReportForm', () => {
  it('names what is being reported', () => {
    render(<ReportForm {...PROPS} />)

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/blow ?down/i)
  })

  it('takes a free-text note', async () => {
    const user = userEvent.setup()
    render(<ReportForm {...PROPS} />)

    await user.type(
      screen.getByRole('textbox', { name: /note/i }),
      'Tree across the trail.',
    )
    await user.click(screen.getByRole('button', { name: /send|save/i }))

    expect(PROPS.onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ note: 'Tree across the trail.' }),
    )
  })

  it('submits without a note - the type and place alone are a valid report', async () => {
    const user = userEvent.setup()
    render(<ReportForm {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /send|save/i }))

    expect(PROPS.onSubmit).toHaveBeenCalled()
  })

  it('stamps the moment of WRITING, taken when the form opened', async () => {
    const user = userEvent.setup()
    render(<ReportForm {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /send|save/i }))

    expect(PROPS.onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ authoredAt: PROPS.now }),
    )
  })

  it('carries the location it was given', async () => {
    const user = userEvent.setup()
    render(<ReportForm {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /send|save/i }))

    expect(PROPS.onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ lat: 35.6, lon: -83.5 }),
    )
  })

  it('shows where the report will be pinned, so it can be checked before sending', () => {
    render(<ReportForm {...PROPS} />)

    expect(screen.getByText(/1,043\.2/)).toBeInTheDocument()
  })

  it('shows how the report will be signed', () => {
    render(<ReportForm {...PROPS} />)

    expect(screen.getByText(/Switchback/)).toHaveTextContent(/thru/i)
  })

  it('offers a photo attachment', () => {
    render(<ReportForm {...PROPS} />)

    expect(screen.getByLabelText(/photo/i)).toBeInTheDocument()
  })

  it('says the report is queued rather than sent, when there is no signal', () => {
    render(<ReportForm {...PROPS} online={false} />)

    expect(screen.getByText(/wait|queue|sync/i)).toBeInTheDocument()
  })

  it('never blocks submission on being online', async () => {
    const user = userEvent.setup()
    render(<ReportForm {...PROPS} online={false} />)

    await user.click(screen.getByRole('button', { name: /send|save/i }))

    expect(PROPS.onSubmit).toHaveBeenCalled()
  })

  it('can be abandoned', async () => {
    const user = userEvent.setup()
    render(<ReportForm {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /cancel|back/i }))

    expect(PROPS.onCancel).toHaveBeenCalled()
  })
})

describe('ReportForm — thanks', () => {
  const THANKS = { ...PROPS, type: 'thanks' as const }

  it('asks for thanks rather than a problem', () => {
    render(<ReportForm {...THANKS} />)

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/thank/i)
  })

  it('names who looks after the stretch, when that is known', () => {
    render(<ReportForm {...THANKS} stewards="Looked after by Mountain Club" />)

    expect(screen.getByText(/Looked after by Mountain Club/)).toBeInTheDocument()
  })

  it('sends fine with nobody resolved - not knowing who is the normal case', async () => {
    const user = userEvent.setup()
    render(<ReportForm {...THANKS} stewards={null} />)

    await user.click(screen.getByRole('button', { name: /send|save/i }))

    expect(THANKS.onSubmit).toHaveBeenCalled()
  })

  it('does not show a severity or seriousness control on a thanks', () => {
    render(<ReportForm {...THANKS} />)

    expect(screen.queryByText(/severity|serious/i)).toBe(null)
  })

  it('never shows a rating or score - this is not a review', () => {
    // SAYING_THANKS.md's non-goals. A star rating here would quietly turn
    // volunteer work into something with a score attached.
    render(<ReportForm {...THANKS} />)

    expect(screen.queryByRole('radiogroup', { name: /rating|stars|score/i })).toBe(null)
    expect(screen.queryByText(/★|rate this/i)).toBe(null)
  })
})
