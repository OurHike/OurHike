import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReportForm } from './ReportForm'
import { PhotoUnusable, prepareReportPhoto } from '../lib/reportPhoto'

// The shrink itself is doubled here and tested for real in
// lib/reportPhoto.test.ts. What this file is about is the FORM's half: that
// the prepared bytes reach `onSubmit`, and that a hiker whose photo cannot be
// prepared is told so and still gets their report sent.
vi.mock('../lib/reportPhoto', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/reportPhoto')>()),
  prepareReportPhoto: vi.fn(),
}))

const mockPrepare = vi.mocked(prepareReportPhoto)

/** What the doubled shrink returns - the same object every time, so a test
 *  can assert the form passed THAT on rather than something Blob-shaped. */
const PREPARED = new Blob([new Uint8Array([9, 9, 9])], { type: 'image/jpeg' })

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
  // Reset per test rather than once: `clearAllMocks` drops the calls but
  // leaves a `mockRejectedValueOnce` from a previous case armed.
  mockPrepare.mockResolvedValue(PREPARED)
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

  it('sends the trail mile it just showed, rather than computing and dropping it', async () => {
    // #244. This form snapped the fix to the centerline to render "mi 1,043.2"
    // and then submitted lat/lon alone, so the one number the serious-warnings
    // banner filters on was discarded at the moment it was known - and nothing
    // server-side can re-derive it, because the backend holds no centerline.
    const user = userEvent.setup()
    render(<ReportForm {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /send|save/i }))

    expect(PROPS.onSubmit).toHaveBeenCalledWith(expect.objectContaining({ mile: 1043.2 }))
  })

  it('omits the mile rather than zeroing it when there is no fix', async () => {
    // Mile 0 is Springer Mountain - the same reason 0,0 is not a stand-in for
    // missing coordinates. A zeroed mile would put every fixless report on the
    // banner of every hiker starting the trail.
    const user = userEvent.setup()
    render(<ReportForm {...PROPS} location={null} />)

    await user.click(screen.getByRole('button', { name: /send|save/i }))

    expect(vi.mocked(PROPS.onSubmit).mock.calls[0][0].mile).toBeUndefined()
  })

  it('shows how the report will be signed', () => {
    render(<ReportForm {...PROPS} />)

    expect(screen.getByText(/Switchback/)).toHaveTextContent(/thru/i)
  })

  // #89 disabled this field because there was nowhere to upload to; #234
  // built the endpoint, so it works now. What it must not do is go back to
  // the original bug - a control that accepts a photo and files a report
  // without it - which is why every case below is about the picked file
  // actually reaching `onSubmit`, or about the hiker being told it will not.
  describe('the photo field', () => {
    const A_PHOTO = new File(['pretend jpeg'], 'bridge.jpg', { type: 'image/jpeg' })

    /** Waits for the picked file to have been through the shrink, which is
     *  async - the attached line appearing is what proves it finished, and
     *  asserting on anything before it would be asserting on a half-run pick. */
    async function attach(user: ReturnType<typeof userEvent.setup>, file = A_PHOTO) {
      await user.upload(screen.getByLabelText(/photo/i), file)
      await screen.findByText(/photo attached/i)
    }

    it('accepts a file, now that there is somewhere to send it', () => {
      render(<ReportForm {...PROPS} />)

      expect(screen.getByLabelText(/photo/i)).toBeEnabled()
    })

    it('sends the PREPARED bytes, not the file the hiker picked', async () => {
      // The original file carries EXIF and several megabytes; what goes in
      // the outbox is what came back from lib/reportPhoto.ts.
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      render(<ReportForm {...PROPS} onSubmit={onSubmit} />)

      await attach(user)
      await user.click(screen.getByRole('button', { name: /send|save/i }))

      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ photo: PREPARED }))
    })

    it('leaves the key off entirely when no photo was picked', async () => {
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      render(<ReportForm {...PROPS} onSubmit={onSubmit} />)

      await user.click(screen.getByRole('button', { name: /send|save/i }))

      expect('photo' in onSubmit.mock.calls[0][0]).toBe(false)
    })

    it('says the location and camera details are not included', async () => {
      // The strip is invisible, and a hiker filing a `bad_hikers` report has
      // a real reason to want to know it happened.
      const user = userEvent.setup()
      render(<ReportForm {...PROPS} />)

      await attach(user)

      expect(screen.getByText(/not included/i)).toBeInTheDocument()
    })

    it('shows the refusal in the words the hiker can act on', async () => {
      const user = userEvent.setup()
      mockPrepare.mockRejectedValueOnce(new PhotoUnusable('Too big. Try taking another.'))
      render(<ReportForm {...PROPS} />)

      await user.upload(screen.getByLabelText(/photo/i), A_PHOTO)

      expect(await screen.findByRole('alert')).toHaveTextContent(/try taking another/i)
    })

    it('does not show an internal error message to a hiker', async () => {
      // Anything that is not a PhotoUnusable was not written to be read on a
      // ridge - a TypeError from a browser quirk, say.
      const user = userEvent.setup()
      mockPrepare.mockRejectedValueOnce(new TypeError('canvas.toBlob is not a function'))
      render(<ReportForm {...PROPS} />)

      await user.upload(screen.getByLabelText(/photo/i), A_PHOTO)

      const alert = await screen.findByRole('alert')
      expect(alert).not.toHaveTextContent(/toBlob/)
      expect(alert).toHaveTextContent(/try taking another/i)
    })

    it('still sends the report when the photo could not be prepared', async () => {
      // The note is what carries the report. Losing the words over the
      // picture would be a worse bug than the one #89 disabled this for.
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      mockPrepare.mockRejectedValueOnce(new PhotoUnusable('No good.'))
      render(<ReportForm {...PROPS} onSubmit={onSubmit} />)

      await user.upload(screen.getByLabelText(/photo/i), A_PHOTO)
      await screen.findByRole('alert')
      await user.click(screen.getByRole('button', { name: /send|save/i }))

      expect(onSubmit).toHaveBeenCalled()
      expect('photo' in onSubmit.mock.calls[0][0]).toBe(false)
    })

    it('drops a previous photo when a second pick fails', async () => {
      // Otherwise the hiker believes they replaced it and the first one is
      // still what gets sent.
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      render(<ReportForm {...PROPS} onSubmit={onSubmit} />)

      await attach(user)
      mockPrepare.mockRejectedValueOnce(new PhotoUnusable('No good.'))
      await user.upload(
        screen.getByLabelText(/photo/i),
        new File(['second'], 'second.jpg', { type: 'image/jpeg' }),
      )
      await screen.findByRole('alert')
      await user.click(screen.getByRole('button', { name: /send|save/i }))

      expect('photo' in onSubmit.mock.calls[0][0]).toBe(false)
    })

    it('does not let the report go while the photo is still being shrunk', async () => {
      // Submitting mid-shrink would file the report without the photo that
      // is moments from being ready - the original bug, on a timer.
      const user = userEvent.setup()
      let finish: (blob: Blob) => void = () => {}
      mockPrepare.mockReturnValueOnce(
        new Promise<Blob>((resolve) => {
          finish = resolve
        }),
      )
      render(<ReportForm {...PROPS} />)

      await user.upload(screen.getByLabelText(/photo/i), A_PHOTO)
      await screen.findByText(/shrinking/i)
      expect(screen.getByRole('button', { name: /send|save/i })).toBeDisabled()

      finish(PREPARED)
      await screen.findByText(/photo attached/i)
      expect(screen.getByRole('button', { name: /send|save/i })).toBeEnabled()
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
