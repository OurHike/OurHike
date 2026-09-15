import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReportForm } from './ReportForm'
import { MAX_REPORT_PHOTOS, PhotoUnusable, prepareReportPhoto } from '../lib/reportPhoto'

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
  describe('the photos (#1439, D17)', () => {
    const A_PHOTO = new File(['pretend jpeg'], 'bridge.jpg', { type: 'image/jpeg' })

    /** Pick one file and wait for its tile to settle. The summary line
     *  counting it is what proves the shrink finished; asserting on anything
     *  before it would be asserting on a half-run pick. */
    async function attach(
      user: ReturnType<typeof userEvent.setup>,
      file = A_PHOTO,
      expected = 1,
    ) {
      await user.upload(screen.getByLabelText(/add a photo/i), file)
      await screen.findByText(
        new RegExp(`${expected} photo${expected === 1 ? '' : 's'} ·`),
      )
    }

    const send = () => screen.getByRole('button', { name: /send|save/i })

    it('sends BOTH, however slowly the first one shrinks', async () => {
      // #657's race, and the acceptance case for replacing the single field.
      // Pick A (a slow HEIC), then B before A finishes. With one slot, B
      // attached and then A resolved over it, so the hiker sent the photo
      // they believed they had replaced - with "Photo attached" showing
      // throughout. With a tile each there is nothing to overwrite: A lands
      // in A's tile whenever it finishes, and both go.
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      const SLOW = new Blob(['first'], { type: 'image/jpeg' })
      const FAST = new Blob(['second'], { type: 'image/jpeg' })

      let releaseSlow: (value: Blob) => void = () => {}
      mockPrepare
        .mockReturnValueOnce(
          new Promise<Blob>((resolve) => {
            releaseSlow = resolve
          }),
        )
        .mockResolvedValueOnce(FAST)

      render(<ReportForm {...PROPS} onSubmit={onSubmit} />)

      await user.upload(screen.getByLabelText(/add a photo/i), A_PHOTO)
      await user.upload(
        screen.getByLabelText(/add a photo/i),
        new File(['second'], 'sign.jpg', { type: 'image/jpeg' }),
      )
      // One has landed, one is still shrinking - and Send is held while any
      // is, so the assertion below is about a settled form.
      await screen.findByText(/1 photo ·/)

      releaseSlow(SLOW)
      await screen.findByText(/2 photos ·/)

      await user.click(send())
      // In pick order, which is the order the tiles are in and the order the
      // outbox numbers them.
      expect(onSubmit.mock.calls[0][0].photos).toEqual([SLOW, FAST])
    })

    it('sends the PREPARED bytes, not the file the hiker picked', async () => {
      // The original file carries EXIF and several megabytes; what goes in
      // the outbox is what came back from lib/reportPhoto.ts.
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      render(<ReportForm {...PROPS} onSubmit={onSubmit} />)

      await attach(user)
      await user.click(send())

      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ photos: [PREPARED] }),
      )
    })

    it('removing one leaves the others attached', async () => {
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      const FIRST = new Blob(['a'], { type: 'image/jpeg' })
      const SECOND = new Blob(['b'], { type: 'image/jpeg' })
      mockPrepare.mockResolvedValueOnce(FIRST).mockResolvedValueOnce(SECOND)
      render(<ReportForm {...PROPS} onSubmit={onSubmit} />)

      await attach(user, A_PHOTO, 1)
      await attach(user, new File(['b'], 'b.jpg', { type: 'image/jpeg' }), 2)

      await user.click(screen.getByRole('button', { name: 'Remove photo 2' }))
      await screen.findByText(/1 photo ·/)
      await user.click(send())

      expect(onSubmit.mock.calls[0][0].photos).toEqual([FIRST])
    })

    it('a failed pick costs its own tile and nothing else', async () => {
      // The acceptance case: A and B attached, C refused. A and B stay, C
      // says why under itself, and Send stays live - the note is what carries
      // the report, and refusing to send would lose the words over a picture.
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      const FIRST = new Blob(['a'], { type: 'image/jpeg' })
      const SECOND = new Blob(['b'], { type: 'image/jpeg' })
      mockPrepare
        .mockResolvedValueOnce(FIRST)
        .mockResolvedValueOnce(SECOND)
        .mockRejectedValueOnce(
          new PhotoUnusable('That file is not an image this can read.'),
        )
      render(<ReportForm {...PROPS} onSubmit={onSubmit} />)

      await attach(user, A_PHOTO, 1)
      await attach(user, new File(['b'], 'b.jpg', { type: 'image/jpeg' }), 2)
      await user.upload(
        screen.getByLabelText(/add a photo/i),
        new File(['c'], 'c.jpg', { type: 'image/jpeg' }),
      )
      await screen.findByText('That file is not an image this can read.')

      // Still two, still countable, and still sendable.
      expect(screen.getByText(/2 photos ·/)).toBeInTheDocument()
      expect(send()).toBeEnabled()

      await user.click(send())
      expect(onSubmit.mock.calls[0][0].photos).toEqual([FIRST, SECOND])
    })

    it('does not show an internal error message to a hiker', async () => {
      const user = userEvent.setup()
      mockPrepare.mockRejectedValueOnce(new TypeError('canvas.toBlob is not a function'))
      render(<ReportForm {...PROPS} />)

      await user.upload(screen.getByLabelText(/add a photo/i), A_PHOTO)

      await screen.findByText(/could not be prepared/i)
      expect(screen.queryByText(/toBlob/)).toBeNull()
    })

    it('sends no photos key of substance when none was picked', async () => {
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      render(<ReportForm {...PROPS} onSubmit={onSubmit} />)

      await user.click(send())

      expect(onSubmit.mock.calls[0][0].photos).toEqual([])
    })

    it('says what is attached and what it weighs', async () => {
      // A hiker about to send over one bar of EDGE is owed the size. Only the
      // ready ones count - a tile still shrinking has no size yet.
      const user = userEvent.setup()
      render(<ReportForm {...PROPS} />)

      await attach(user)

      expect(screen.getByText(/1 photo · \d+ KB so far/)).toBeInTheDocument()
    })

    it('says the location and camera details are not included', async () => {
      // The promise IDENTITY_AND_PRIVACY.md makes, said where a hiker is
      // deciding whether to attach one - and it applies to every tile.
      const user = userEvent.setup()
      render(<ReportForm {...PROPS} />)

      await attach(user)

      expect(
        screen.getByText(/Location and camera details are not included/),
      ).toBeInTheDocument()
    })

    it('does not let the report go while a photo is still being shrunk', async () => {
      // Held only while a shrink is running: sending mid-prepare would file a
      // report whose picture arrives nowhere.
      const user = userEvent.setup()
      let release: (value: Blob) => void = () => {}
      mockPrepare.mockReturnValueOnce(
        new Promise<Blob>((resolve) => {
          release = resolve
        }),
      )
      render(<ReportForm {...PROPS} />)

      await user.upload(screen.getByLabelText(/add a photo/i), A_PHOTO)
      expect(send()).toBeDisabled()

      release(PREPARED)
      await screen.findByText(/1 photo ·/)
      expect(send()).toBeEnabled()
    })

    it('says why rather than greying the control at the ceiling', async () => {
      // D10: a refusal is a sentence, never a disabled control. Past the cap
      // the `+` tile is gone and the sentence says what to do about it.
      const user = userEvent.setup()
      render(<ReportForm {...PROPS} />)

      for (let n = 1; n <= MAX_REPORT_PHOTOS; n += 1) {
        await attach(user, new File([`${n}`], `${n}.jpg`, { type: 'image/jpeg' }), n)
      }

      expect(screen.queryByLabelText(/add a photo/i)).toBeNull()
      expect(
        screen.getByText(new RegExp(`That is ${MAX_REPORT_PHOTOS} photos`)),
      ).toBeInTheDocument()
      // Not a disabled control anywhere on the way out.
      expect(screen.queryByRole('button', { name: /add a photo/i })).toBeNull()
    })
  })

  describe('where this was (#1439, D16)', () => {
    const send = () => screen.getByRole('button', { name: /send|save/i })

    it('offers a way to correct every one of the three states', () => {
      // `describeLocation` had exactly three answers and no way to change any
      // of them, so a hiker who walked on before filing could not say where
      // the tree actually is. The wording of all three is unchanged; what is
      // new is that each is correctable.
      for (const location of [
        { lat: 35.6, lon: -83.5, mile: 1043.2 },
        { lat: 35.6, lon: -83.5 },
        null,
      ]) {
        render(<ReportForm {...PROPS} location={location} onChangeLocation={vi.fn()} />)
        expect(screen.getByRole('button', { name: /change/i })).toBeInTheDocument()
        cleanup()
      }
    })

    it('draws no Change where the shell has no map to offer', () => {
      // D10 again: a control that opens nothing is worse than no control.
      render(<ReportForm {...PROPS} />)

      expect(screen.queryByRole('button', { name: /change/i })).toBeNull()
    })

    it('asks for a place in words only when nothing else can say where', async () => {
      // No fix AND no waypoint behind the report. With either, the question
      // would collect prose nobody needs beside a location the report has.
      render(<ReportForm {...PROPS} location={null} />)
      expect(screen.getByText('Where was this?')).toBeInTheDocument()
      cleanup()

      render(<ReportForm {...PROPS} location={null} poiId="atc_shelters:12" />)
      expect(screen.queryByText('Where was this?')).toBeNull()
      cleanup()

      render(<ReportForm {...PROPS} />)
      expect(screen.queryByText('Where was this?')).toBeNull()
    })

    it("sends the hiker's words and NO coordinates", async () => {
      // The acceptance case, and the pair is the assertion: the words travel
      // and lat/lon/mile stay absent. A typed name turned into coordinates
      // would be a confident wrong dot on every phone that downloads it.
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      render(<ReportForm {...PROPS} location={null} onSubmit={onSubmit} />)

      await user.type(
        // A regex, because the field's accessible name is the whole label -
        // the question AND the line under it, which is what a screen reader
        // should hear and what the form deliberately keeps together.
        screen.getByLabelText(/Where was this\?/),
        'The brook crossing north of Fitzgerald Falls',
      )
      await user.click(send())

      const submitted = onSubmit.mock.calls[0][0]
      expect(submitted.place_words).toBe('The brook crossing north of Fitzgerald Falls')
      expect(submitted.lat).toBeUndefined()
      expect(submitted.lon).toBeUndefined()
      expect(submitted.mile).toBeUndefined()
    })

    it('sends no place key at all when the question went unanswered', async () => {
      // Absent, never an empty string - which would be a claim that somebody
      // answered.
      const user = userEvent.setup()
      const onSubmit = vi.fn()
      render(<ReportForm {...PROPS} location={null} onSubmit={onSubmit} />)

      await user.click(send())

      expect('place_words' in onSubmit.mock.calls[0][0]).toBe(false)
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
