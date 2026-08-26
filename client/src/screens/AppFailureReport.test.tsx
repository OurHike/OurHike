import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AppFailureReport } from './AppFailureReport'
import { readBuildInfo } from '../lib/buildInfo'

// #848. This screen exists because the four options in ReportBug.tsx are all
// links into GitHub, and the app failing while somebody navigates by it
// happens where there is no signal and where a public issue tracker cannot
// hold the one field that matters - a way to reach the person who wrote it.
//
// So what is worth pinning here is not that a form submits. It is the four
// promises the screen makes to a hiker who has just been frightened: that
// what they type is kept, that their contact detail does not become public,
// that nothing is taken from them silently, and that they are told whether
// anybody can actually get back to them.

const RELEASE = readBuildInfo({
  version: '1.0.0',
  commit: '6e23f122d35c327abf6eec8ca48158e336362cc9',
  builtAt: '2026-08-07T23:51:31.603Z',
})

const WRITTEN = new Date('2026-08-12T14:05:00.000Z')

afterEach(cleanup)

function renderForm(props: Partial<Parameters<typeof AppFailureReport>[0]> = {}) {
  const onSubmit = vi.fn()
  const onClose = vi.fn()
  render(
    <AppFailureReport
      build={RELEASE}
      now={WRITTEN}
      onSubmit={onSubmit}
      onClose={onClose}
      {...props}
    />,
  )
  return { onSubmit, onClose }
}

const what = () => screen.getByLabelText(/what happened/i)
const send = () => screen.getByRole('button', { name: /send|save to outbox/i })

describe('AppFailureReport', () => {
  it('files what the hiker wrote, and how to reach them', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()

    await user.type(what(), 'The map went blank while I was following it.')
    await user.type(screen.getByLabelText(/where were you/i), 'the ford below Fontana')
    await user.type(screen.getByLabelText(/reach you/i), 'sparrow@example.com')

    await user.click(send())

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const [draft] = onSubmit.mock.calls[0]
    expect(draft.what_happened).toBe('The map went blank while I was following it.')
    expect(draft.whereabouts).toBe('the ford below Fontana')
    expect(draft.contact).toBe('sparrow@example.com')
  })

  it('records which of the four harms it came near, for triage', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()

    await user.type(what(), 'It stopped drawing my position.')
    await user.click(screen.getByLabelText(/didn’t know where I was/i))
    await user.click(screen.getByLabelText(/ran out of water/i))
    await user.click(send())

    expect(onSubmit.mock.calls[0][0].harms).toEqual(['lost', 'water'])
  })

  it('treats ticking nothing as an answer rather than a blank', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()

    await user.type(what(), 'It stopped drawing my position.')
    await user.click(send())

    expect(onSubmit.mock.calls[0][0].harms).toEqual([])
  })

  // Both of these are omitted rather than sent empty: an empty string is a
  // claim that they answered and had nothing to say.
  it('leaves out the fields nobody filled in', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()

    await user.type(what(), 'It stopped drawing my position.')
    await user.click(send())

    const [draft] = onSubmit.mock.calls[0]
    expect('whereabouts' in draft).toBe(false)
    expect('contact' in draft).toBe(false)
  })

  it('carries this build, without anybody retyping a commit', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()

    await user.type(what(), 'It stopped drawing my position.')
    await user.click(send())

    expect(onSubmit.mock.calls[0][0].build).toContain(
      '6e23f122d35c327abf6eec8ca48158e336362cc9',
    )
  })

  // The single most diagnostic fact about this class of failure, and the one
  // bug_report.yml already asks for in words.
  it('says whether the phone had signal while it was being written', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm({ online: false })

    await user.type(what(), 'It stopped drawing my position.')
    await user.click(screen.getByRole('button', { name: /save to outbox/i }))

    expect(onSubmit.mock.calls[0][0].was_offline).toBe(true)
  })

  // The authoring time is taken at MOUNT: somebody can start this, walk on,
  // and finish it twenty minutes later, and what matters is when it happened.
  it('stamps the report with when it was started, not when it was sent', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()

    await user.type(what(), 'It stopped drawing my position.')
    await user.click(send())

    expect(onSubmit.mock.calls[0][1]).toEqual(WRITTEN)
  })

  it('will not file a report with nothing in it', async () => {
    renderForm()

    // Nothing to store and nothing to act on. Everything else on this form is
    // optional; this is the field that makes it a report.
    expect(send()).toBeDisabled()
  })

  // --- what it promises, in words on the screen --------------------------

  it('says where the contact detail goes, next to the field asking for it', () => {
    renderForm()

    const promise = screen.getByText(/never goes on the public issue tracker/i)
    expect(promise).toBeInTheDocument()
  })

  it('says what is attached without being typed, and that location is not', () => {
    renderForm({ online: false })

    expect(screen.getByText(/Attached:/)).toHaveTextContent('no signal')
    expect(screen.getByText(/location is not attached/i)).toBeInTheDocument()
  })

  it('says plainly that this one works with no signal and no account', () => {
    renderForm({ online: false })

    const note = screen.getByText(/wait in your outbox/i)
    expect(note).toHaveTextContent(/do not need an account/i)
  })

  // --- the acknowledgement ----------------------------------------------

  it('tells a hiker who left a contact that somebody will get back to them', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.type(what(), 'It stopped drawing my position.')
    await user.type(screen.getByLabelText(/reach you/i), 'sparrow@example.com')
    await user.click(send())

    expect(await screen.findByText(/somebody will get back to you/i)).toBeInTheDocument()
  })

  // The half worth being blunt about. A reply somebody is waiting for and
  // never gets is worse than being told there will not be one.
  it('tells a hiker who left none that nobody can reply', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.type(what(), 'It stopped drawing my position.')
    await user.click(send())

    expect(await screen.findByText(/nobody can reply/i)).toBeInTheDocument()
  })

  it('says the report is waiting rather than sent when there is no signal', async () => {
    const user = userEvent.setup()
    renderForm({ online: false })

    await user.type(what(), 'It stopped drawing my position.')
    await user.click(screen.getByRole('button', { name: /save to outbox/i }))

    expect(await screen.findByText(/waiting in your outbox/i)).toBeInTheDocument()
  })

  it('stays open on the acknowledgement until the hiker closes it', async () => {
    const user = userEvent.setup()
    const { onClose } = renderForm()

    await user.type(what(), 'It stopped drawing my position.')
    await user.click(send())
    expect(onClose).not.toHaveBeenCalled()

    await user.click(await screen.findByRole('button', { name: /done/i }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('cannot file the same report twice from the acknowledgement', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()

    await user.type(what(), 'It stopped drawing my position.')
    await user.click(send())

    await screen.findByRole('button', { name: /done/i })
    expect(screen.queryByRole('button', { name: /^send$/i })).not.toBeInTheDocument()
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  // The acknowledgement is a claim that the words are kept, and writing to
  // IndexedDB can genuinely fail - a phone with no space left is a real state
  // in this app (lib/storageHealth.ts). Saying "that is saved" over a write
  // that did not happen is the one lie this screen must not tell.
  it('does not claim the report is saved when saving it failed', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockRejectedValue(new Error('no space left'))
    render(
      <AppFailureReport
        build={RELEASE}
        now={WRITTEN}
        onSubmit={onSubmit}
        onClose={vi.fn()}
      />,
    )

    await user.type(what(), 'The map went blank.')
    await user.click(send())

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not save/i)
    expect(screen.queryByText(/that is saved/i)).not.toBeInTheDocument()
  })

  it('keeps what was typed when the save failed, so it can still be copied out', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockRejectedValue(new Error('no space left'))
    render(
      <AppFailureReport
        build={RELEASE}
        now={WRITTEN}
        onSubmit={onSubmit}
        onClose={vi.fn()}
      />,
    )

    await user.type(what(), 'The map went blank.')
    await user.click(send())
    await screen.findByRole('alert')

    // The only thing left that keeps the words is the hiker copying them, and
    // they can only do that while they are still on the screen.
    expect(what()).toHaveValue('The map went blank.')
  })

  it('leaves without filing anything when cancelled', async () => {
    const user = userEvent.setup()
    const { onSubmit, onClose } = renderForm()

    await user.type(what(), 'half a thought')
    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
