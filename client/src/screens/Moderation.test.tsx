import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Moderation, ageOf } from './Moderation'
import * as api from '../lib/api'

// #235: the moderation queue existed as four HTTP endpoints and no surface, so
// a `bad_hikers` report - one about being followed on trail - reached the
// audience `internal_only` names only if somebody ran curl.
//
// Three properties carry most of this file:
//
//  1. **A queue that could not be read is not an empty queue.** They draw the
//     same screen and mean opposite things, and the wrong one tells a
//     moderator there are no unreviewed safety reports.
//  2. **`bad_hikers` is not a row in the same list**, and is also not filtered
//     out. Rendering it identically decides it is the same kind of decision;
//     dropping it re-opens the hole #230 closed.
//  3. **Verify sends no severity unless one was chosen** (#251). An explicit
//     `normal` is a de-escalation that clears the flag putting a warning pin
//     on every phone on the trail.
//  4. **A photo is either shown or accounted for in words** (#385). Never
//     drawn as absence - a broken image and a report with no photo look
//     identical, and one of them means a moderator decided without evidence
//     they were entitled to see.

vi.mock('../lib/api', () => ({
  fetchModerationQueue: vi.fn(),
  fetchReportPhotoLink: vi.fn(),
  verifyReport: vi.fn(),
  dismissReport: vi.fn(),
  verifyClosure: vi.fn(),
  dismissClosure: vi.fn(),
}))

const mocked = vi.mocked(api)

function aReport(over: Partial<api.QueuedReport> = {}): api.QueuedReport {
  return {
    id: 'report-1',
    type: 'blowdown',
    reporter_type: 'thru',
    status: 'submitted',
    severity: 'normal',
    lat: 35.6,
    lon: -83.5,
    poi_id: null,
    note: 'Large tree across the trail.',
    timestamp: new Date().toISOString(),
    visibility: 'public',
    photo_url: null,
    reporter_id: 'hiker-1',
    ...over,
  }
}

function aClosure(over: Partial<api.QueuedClosure> = {}): api.QueuedClosure {
  return {
    id: 'closure-1',
    reason_type: 'storm_damage',
    note: 'Bridge out after the storm.',
    status: 'closed',
    start_mile_marker: 100,
    end_mile_marker: 120,
    reported_at: new Date().toISOString(),
    ...over,
  }
}

/** Renders and waits for the first read to have finished, which is async -
 *  asserting before it would be asserting on the loading state. */
async function shown(queue: Partial<api.ModerationQueue> = {}) {
  mocked.fetchModerationQueue.mockResolvedValue({
    reports: [],
    closures: [],
    ...queue,
  })
  render(<Moderation onClose={vi.fn()} />)
  await screen.findByRole('heading', { level: 1 })
  await waitFor(() => expect(screen.queryByText(/reading the queue/i)).toBeNull())
}

/** The object key the backend stores in `photo_url` - what "has a photo"
 *  actually looks like on the wire. Never a URL: see app/core/photos.py. */
const PHOTO_KEY = 'reports/report-1/1.jpg'

beforeEach(() => {
  vi.clearAllMocks()
  mocked.verifyReport.mockResolvedValue(undefined)
  mocked.dismissReport.mockResolvedValue(undefined)
  mocked.verifyClosure.mockResolvedValue(undefined)
  mocked.dismissClosure.mockResolvedValue(undefined)
  mocked.fetchReportPhotoLink.mockResolvedValue({
    url: 'https://photos.example/signed',
    expiresIn: 300,
  })
})

afterEach(() => {
  cleanup()
})

describe('the moderation queue', () => {
  it('lists a waiting report with what the decision turns on', async () => {
    await shown({ reports: [aReport()] })

    expect(screen.getByText(/blow ?down/i)).toBeInTheDocument()
    expect(screen.getByText(/large tree across the trail/i)).toBeInTheDocument()
    // Reporter type and place both matter: a thru-hiker at a named mile is a
    // different weight of evidence from a day hiker with no fix.
    expect(screen.getByText(/thru/)).toBeInTheDocument()
    expect(screen.getByText(/35\.6/)).toBeInTheDocument()
  })

  it('lists a waiting closure alongside it, in the same queue', async () => {
    // REPORT_A_PROBLEM.md: closures reuse this workflow rather than growing a
    // second review mechanism.
    await shown({ closures: [aClosure()] })

    expect(screen.getByText(/bridge out after the storm/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /publish closure/i })).toBeInTheDocument()
  })

  it('says a queue it could not read is not a queue of nothing', async () => {
    mocked.fetchModerationQueue.mockRejectedValue(new Error('no signal'))
    render(<Moderation onClose={vi.fn()} />)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/not a list of nothing waiting/i)
    // And specifically not the words an empty queue uses.
    expect(screen.queryByText(/nothing waiting\./i)).toBeNull()
  })

  it('can be retried after a failed read', async () => {
    const user = userEvent.setup()
    mocked.fetchModerationQueue.mockRejectedValueOnce(new Error('no signal'))
    mocked.fetchModerationQueue.mockResolvedValue({ reports: [aReport()], closures: [] })
    render(<Moderation onClose={vi.fn()} />)
    await screen.findByRole('alert')

    await user.click(screen.getByRole('button', { name: /try again/i }))

    expect(await screen.findByText(/large tree/i)).toBeInTheDocument()
  })
})

describe('a report about a person', () => {
  const BAD_HIKER = aReport({
    id: 'bad-1',
    type: 'bad_hikers',
    visibility: 'internal_only',
  })

  it('is shown, not filtered out', async () => {
    // The backend includes it deliberately - `internal_only` names exactly
    // this audience. A client that dropped it would put the report back where
    // #230 found it: reaching nobody but its own author.
    await shown({ reports: [BAD_HIKER] })

    expect(screen.getByText(/someone unsafe/i)).toBeInTheDocument()
  })

  it('is kept out of the trail-conditions list, in its own section', async () => {
    await shown({ reports: [BAD_HIKER, aReport()] })

    const people = screen
      .getByRole('heading', { name: /about a person/i })
      .closest('section')
    const trail = screen
      .getByRole('heading', { name: /trail conditions/i })
      .closest('section')

    expect(people).toHaveTextContent(/someone unsafe/i)
    expect(people).not.toHaveTextContent(/blow ?down/i)
    expect(trail).toHaveTextContent(/blow ?down/i)
    expect(trail).not.toHaveTextContent(/someone unsafe/i)
  })

  it('says out loud which questions about it are still undecided', async () => {
    // Routing (which club) and the corroboration bar are both named as open
    // in REPORT_A_PROBLEM.md and HIKER_SAFETY.md. A screen that said nothing
    // would have answered them by omission.
    await shown({ reports: [BAD_HIKER] })

    const people = screen
      .getByRole('heading', { name: /about a person/i })
      .closest('section')
    expect(people).toHaveTextContent(/undecided/i)
  })

  it('has its own empty state rather than vanishing when none are waiting', async () => {
    // A section that disappears when empty cannot be distinguished from one
    // that was never built.
    await shown({ reports: [aReport()] })

    const people = screen
      .getByRole('heading', { name: /about a person/i })
      .closest('section')
    expect(people).toHaveTextContent(/nothing waiting/i)
  })
})

describe('acting on the queue', () => {
  it('confirms a report WITHOUT saying anything about severity', async () => {
    // #251: an omitted severity means "said nothing"; an explicit `normal`
    // de-escalates. Sending one by default clears another moderator's
    // `serious` flag and the warning pin that flag creates.
    const user = userEvent.setup()
    await shown({ reports: [aReport()] })

    await user.click(screen.getByRole('button', { name: /^confirm$/i }))

    expect(mocked.verifyReport).toHaveBeenCalledWith('report-1')
    expect(mocked.verifyReport.mock.calls[0]).toHaveLength(1)
  })

  it('escalates in the same action rather than as a second step', async () => {
    // HIKER_SAFETY.md §1: "the same review step, not a second one".
    const user = userEvent.setup()
    await shown({ reports: [aReport()] })

    await user.click(screen.getByRole('button', { name: /confirm as serious/i }))

    expect(mocked.verifyReport).toHaveBeenCalledWith('report-1', 'serious')
  })

  it('dismisses a report', async () => {
    const user = userEvent.setup()
    await shown({ reports: [aReport()] })

    await user.click(screen.getByRole('button', { name: /dismiss/i }))

    expect(mocked.dismissReport).toHaveBeenCalledWith('report-1')
  })

  it('publishes and dismisses a closure', async () => {
    const user = userEvent.setup()
    await shown({ closures: [aClosure()] })

    await user.click(screen.getByRole('button', { name: /publish closure/i }))
    expect(mocked.verifyClosure).toHaveBeenCalledWith('closure-1')

    await user.click(screen.getByRole('button', { name: /dismiss/i }))
    expect(mocked.dismissClosure).toHaveBeenCalledWith('closure-1')
  })

  it('re-reads the queue afterwards rather than patching the list', async () => {
    // A club has more than one moderator, so what this screen believes is
    // waiting goes stale the moment somebody else acts. Re-reading is the
    // difference between a stale row and a 404 on the next click.
    const user = userEvent.setup()
    await shown({ reports: [aReport()] })
    expect(mocked.fetchModerationQueue).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole('button', { name: /^confirm$/i }))

    await waitFor(() => expect(mocked.fetchModerationQueue).toHaveBeenCalledTimes(2))
  })

  it('does not swallow a failed action into a silent no-op', async () => {
    // The row would otherwise stay on screen looking untouched, which reads
    // as "not done yet" for something that was attempted and refused.
    const user = userEvent.setup()
    await shown({ reports: [aReport()] })
    mocked.verifyReport.mockRejectedValue(new Error('refused'))

    await user.click(screen.getByRole('button', { name: /^confirm$/i }))

    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})

describe('the photo the decision turns on', () => {
  // #385. The screen used to say "has a photo, which this screen cannot show
  // yet", because the obvious `<img src={.../photo}>` fails silently: an
  // `<img>` carries no token, the endpoint's optional auth answers anonymous
  // callers with the public view, and an `internal_only` photo comes back 404
  // as a broken image. The fix is a URL fetched WITH the token and put in
  // `src` - so what these cases hold is that every path either shows the
  // image or says why it is not showing it.

  it('shows a trail photo, from a URL asked for with the token', async () => {
    await shown({ reports: [aReport({ photo_url: PHOTO_KEY })] })

    const photo = await screen.findByRole('img')
    expect(photo).toHaveAttribute('src', 'https://photos.example/signed')
    expect(mocked.fetchReportPhotoLink).toHaveBeenCalledWith(
      'report-1',
      expect.anything(),
    )
  })

  it('draws nothing at all about photos for a report that has none', async () => {
    // The other half of "never draw absence over a photo": absence still has
    // to read as absence when it is real.
    await shown({ reports: [aReport({ photo_url: null })] })

    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.queryByText(/photo/i)).toBeNull()
    expect(mocked.fetchReportPhotoLink).not.toHaveBeenCalled()
  })

  it('says a photo it was refused rather than showing an empty row', async () => {
    // The exact failure #385 is about, now with words on it. A moderator who
    // knows evidence exists and is not reaching them can wait for it; one
    // shown a blank row decides without it and cannot know they did.
    mocked.fetchReportPhotoLink.mockRejectedValue(new Error('404'))
    await shown({ reports: [aReport({ photo_url: PHOTO_KEY })] })

    expect(await screen.findByText(/could not be loaded/i)).toBeInTheDocument()
    expect(screen.queryByRole('img')).toBeNull()
  })

  it('asks for a fresh URL when the image will not load, rather than breaking', async () => {
    // A link is good for minutes and a queue is worked through over an hour,
    // so the one at the bottom of the list is routinely expired by the time
    // it renders. Re-asking is what let the TTL stay short (#385).
    mocked.fetchReportPhotoLink
      .mockResolvedValueOnce({ url: 'https://photos.example/expired', expiresIn: 300 })
      .mockResolvedValueOnce({ url: 'https://photos.example/fresh', expiresIn: 300 })
    await shown({ reports: [aReport({ photo_url: PHOTO_KEY })] })

    const stale = await screen.findByRole('img')
    expect(stale).toHaveAttribute('src', 'https://photos.example/expired')

    fireEvent.error(stale)

    // Waited on the rendered src rather than the call count: the second call
    // starting proves nothing about the image the moderator ends up looking
    // at, and this assertion cannot pass until that render has happened.
    await waitFor(() =>
      expect(screen.getByRole('img')).toHaveAttribute(
        'src',
        'https://photos.example/fresh',
      ),
    )
    expect(mocked.fetchReportPhotoLink).toHaveBeenCalledTimes(2)
  })

  it('stops after a second failure and says so, rather than re-asking forever', async () => {
    // Two failures in a row is not an expired link - it is an object that
    // never landed, or R2 refusing. A retry loop against that spends the
    // moderator's connection and still shows them nothing.
    mocked.fetchReportPhotoLink
      .mockResolvedValueOnce({ url: 'https://photos.example/one', expiresIn: 300 })
      .mockResolvedValueOnce({ url: 'https://photos.example/two', expiresIn: 300 })
    await shown({ reports: [aReport({ photo_url: PHOTO_KEY })] })

    fireEvent.error(await screen.findByRole('img'))
    await waitFor(() =>
      expect(screen.getByRole('img')).toHaveAttribute(
        'src',
        'https://photos.example/two',
      ),
    )
    fireEvent.error(screen.getByRole('img'))

    expect(await screen.findByText(/could not be loaded/i)).toBeInTheDocument()
    expect(mocked.fetchReportPhotoLink).toHaveBeenCalledTimes(2)
  })

  it('recovers again after one that loaded, because links keep expiring', async () => {
    // The retry budget is per link, not per screen. A queue left open all
    // afternoon expires its links repeatedly, and a component that spent its
    // one retry at 09:00 would show a broken image for the rest of the day.
    mocked.fetchReportPhotoLink
      .mockResolvedValueOnce({ url: 'https://photos.example/one', expiresIn: 300 })
      .mockResolvedValueOnce({ url: 'https://photos.example/two', expiresIn: 300 })
      .mockResolvedValueOnce({ url: 'https://photos.example/three', expiresIn: 300 })
    await shown({ reports: [aReport({ photo_url: PHOTO_KEY })] })

    fireEvent.error(await screen.findByRole('img'))
    await waitFor(() =>
      expect(screen.getByRole('img')).toHaveAttribute(
        'src',
        'https://photos.example/two',
      ),
    )
    // This one rendered - and then expired an hour later.
    fireEvent.load(screen.getByRole('img'))
    fireEvent.error(screen.getByRole('img'))

    await waitFor(() =>
      expect(screen.getByRole('img')).toHaveAttribute(
        'src',
        'https://photos.example/three',
      ),
    )
  })

  it('offers a retry after giving up, without re-reading the whole queue', async () => {
    // Otherwise the only way back is a queue re-read, which for a moderator
    // mid-decision means losing their place over one failed image.
    const user = userEvent.setup()
    mocked.fetchReportPhotoLink.mockRejectedValueOnce(new Error('502'))
    mocked.fetchReportPhotoLink.mockResolvedValue({
      url: 'https://photos.example/signed',
      expiresIn: 300,
    })
    await shown({ reports: [aReport({ photo_url: PHOTO_KEY })] })
    await screen.findByText(/could not be loaded/i)

    await user.click(screen.getByRole('button', { name: /try the photo again/i }))

    expect(await screen.findByRole('img')).toHaveAttribute(
      'src',
      'https://photos.example/signed',
    )
  })
})

describe('a photo of a person', () => {
  const BAD_HIKER_PHOTO = aReport({
    id: 'bad-1',
    type: 'bad_hikers',
    visibility: 'internal_only',
    photo_url: 'reports/bad-1/1.jpg',
  })

  it('is not fetched until a moderator asks for it', async () => {
    // #385 leaves thumbnail-versus-click-to-reveal open, and this is the
    // answer that can be undone later. A queue rendering twenty faces has
    // decided scrolling past is the same act as looking.
    await shown({ reports: [BAD_HIKER_PHOTO] })

    expect(screen.queryByRole('img')).toBeNull()
    expect(mocked.fetchReportPhotoLink).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /show the photo/i })).toBeInTheDocument()
  })

  it('is shown when they do ask', async () => {
    // The step is deliberate, not a refusal - the moderator is the audience
    // `internal_only` names, and this is the evidence they are deciding on.
    const user = userEvent.setup()
    await shown({ reports: [BAD_HIKER_PHOTO] })

    await user.click(screen.getByRole('button', { name: /show the photo/i }))

    expect(await screen.findByRole('img')).toHaveAttribute(
      'src',
      'https://photos.example/signed',
    )
    expect(mocked.fetchReportPhotoLink).toHaveBeenCalledWith('bad-1', expect.anything())
  })

  it('says a photo is there while it is still waiting to be asked for', async () => {
    // Otherwise the button is the only sign, and a button that says nothing
    // about what is behind it is a report that looks like it has no evidence.
    await shown({ reports: [BAD_HIKER_PHOTO] })

    expect(screen.getByText(/this report has a photo/i)).toBeInTheDocument()
  })
})

describe('ageOf', () => {
  const NOW = new Date('2026-08-07T12:00:00Z')

  it('counts minutes below an hour', () => {
    expect(ageOf('2026-08-07T11:23:00Z', NOW)).toBe('37m')
  })

  it('counts hours below a day', () => {
    expect(ageOf('2026-08-07T04:00:00Z', NOW)).toBe('8h')
  })

  it('counts days after that', () => {
    expect(ageOf('2026-08-04T12:00:00Z', NOW)).toBe('3d')
  })

  it('does not render a negative age from a phone with a fast clock', () => {
    // The same wrong-clock case the outbox already handles (#266). "-4m" in a
    // queue reads as a bug in the queue rather than a bug in a phone.
    expect(ageOf('2026-08-07T12:04:00Z', NOW)).toBe('just now')
  })

  it('says something rather than NaN for an unparseable timestamp', () => {
    expect(ageOf('not a date', NOW)).toBe('just now')
  })
})
