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

  it('files no coordinates at all rather than 0,0 when there is no fix', async () => {
    // The bug: the shell passed lat 0 / lon 0 / mile 0 whenever the GPS had not
    // reported yet, so a report written at a trailhead with no sky view was
    // filed at Null Island - and, by its mile, at Springer Mountain. Both are
    // confident, checkable-looking answers, which is what makes them worse
    // than an absent one. The reports API takes lat and lon as optional.
    const user = userEvent.setup()
    render(<ReportForm {...PROPS} location={null} />)

    await user.click(screen.getByRole('button', { name: /send|save/i }))

    const submission = vi.mocked(PROPS.onSubmit).mock.calls[0][0]
    expect(submission.lat).toBeUndefined()
    expect(submission.lon).toBeUndefined()
    // Still a report worth filing: a blowdown with no coordinates is a real
    // contribution, and dropping it would cost more than the missing pin.
    expect(submission.type).toBe('blowdown')
  })

  it('says the location is unknown instead of showing mile zero', () => {
    render(<ReportForm {...PROPS} location={null} />)

    expect(screen.getByText(/no gps fix/i)).toBeInTheDocument()
    expect(screen.queryByText(/mi 0\.0/)).not.toBeInTheDocument()
  })

  it('still sends the coordinates when only the trail mile is unknown', async () => {
    // Being off the centerline, or not having downloaded the trail index yet,
    // says nothing about the fix itself - it is the mile alone that cannot be
    // worked out, and a maintainer can still find the spot from lat/lon.
    const user = userEvent.setup()
    render(<ReportForm {...PROPS} location={{ lat: 35.6, lon: -83.5 }} />)

    expect(screen.getByText(/not matched to a trail mile/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /send|save/i }))

    expect(PROPS.onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ lat: 35.6, lon: -83.5 }),
    )
  })

  it('shows how the report will be signed', () => {
    render(<ReportForm {...PROPS} />)

    expect(screen.getByText(/Switchback/)).toHaveTextContent(/thru/i)
  })

  // The photo field accepted a file and threw it away. There was no onChange,
  // no ref and no state behind the input, so a hiker photographing a
  // washed-out bridge got a control that took the photo and a report that
  // arrived without it - with nothing indicating the loss.
  //
  // The backend half is finished; what does not exist is anywhere to upload
  // to, and picking between R2 and Supabase Storage is a decision rather than
  // a task. Until it is made, the honest control is one that does not pretend.
  describe('the photo field', () => {
    it('does not accept a file it has nowhere to send', () => {
      render(<ReportForm {...PROPS} />)

      expect(screen.getByLabelText(/photo/i)).toBeDisabled()
    })

    it('says why, rather than looking broken', () => {
      // A hiker who took a photo specifically to attach would otherwise be
      // left wondering whether they had missed the button.
      render(<ReportForm {...PROPS} />)

      expect(screen.getByText(/can.t be attached yet/i)).toBeInTheDocument()
    })

    it('points at the note as the thing that does carry the report', () => {
      render(<ReportForm {...PROPS} />)

      expect(screen.getByText(/describe what you saw in the note/i)).toBeInTheDocument()
    })

    it('ties the explanation to the control for a screen reader', () => {
      // A disabled input a screen reader announces with no reason attached is
      // the same dead end as an unexplained one on screen.
      render(<ReportForm {...PROPS} />)

      expect(screen.getByLabelText(/photo/i)).toHaveAccessibleDescription(
        /can.t be attached yet/i,
      )
    })

    it('still submits the report the note carries', () => {
      // The field being unavailable must not block the thing that does work.
      // Whatever else is true, the washed-out bridge has to get reported.
      const onSubmit = vi.fn()
      render(<ReportForm {...PROPS} onSubmit={onSubmit} />)

      return userEvent
        .type(screen.getByRole('textbox'), 'Bridge is out at the creek')
        .then(() =>
          userEvent.click(screen.getByRole('button', { name: /send|submit|report/i })),
        )
        .then(() => {
          expect(onSubmit).toHaveBeenCalled()
        })
    })
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
