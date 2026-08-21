import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ClosureForm } from './ClosureForm'

// The closure form (#832). Three properties, and the first one is the whole
// design decision:
//
//  1. **The far end is optional, and blank does not become a guess.** Nobody
//     standing at a washout can see where the closure ends. A made-up far end
//     is a stretch somebody drew, and it gets drawn as a band on every phone
//     that downloads it.
//  2. **A missing start mile is refused rather than filed as zero.** mi 0.0 is
//     Springer Mountain - a real place two thousand miles from most washouts.
//  3. **The screen says what filing this does**, because a hiker who believes
//     they have just closed a trail for everybody files differently from one
//     who knows they are telling a club.

afterEach(() => {
  cleanup()
})

function shown(over: Partial<Parameters<typeof ClosureForm>[0]> = {}) {
  const onSubmit = vi.fn()
  render(
    <ClosureForm
      hereMile={1408.63}
      onSubmit={onSubmit}
      onCancel={vi.fn()}
      now={new Date('2026-08-21T14:00:00.000Z')}
      {...over}
    />,
  )
  return onSubmit
}

describe('the closure form', () => {
  it('prefills the mile the hiker is standing at, to a tenth', () => {
    shown()

    // A tenth, because that is the precision the header prints and the
    // precision a mile marker carries. More digits would claim a survey.
    expect(screen.getByDisplayValue('1408.6')).toBeTruthy()
  })

  it('files the same mile twice when the far end is unknown', async () => {
    const onSubmit = shown()

    await userEvent.click(screen.getByRole('button', { name: /send/i }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const submission = onSubmit.mock.calls[0][0]
    expect(submission.startMile).toBe(1408.6)
    // Not a guessed span. "It is shut here and I could not see how far it
    // runs" is a point, and the moderator sets the real extent.
    expect(submission.endMile).toBe(1408.6)
  })

  it('takes a far end when the reporter does know one', async () => {
    const onSubmit = shown()

    await userEvent.type(screen.getByLabelText(/to mile/i), '1411.2')
    await userEvent.click(screen.getByRole('button', { name: /send/i }))

    const submission = onSubmit.mock.calls[0][0]
    expect(submission.endMile).toBe(1411.2)
  })

  it('asks for a mile rather than filing one at Springer Mountain', async () => {
    const onSubmit = shown({ hereMile: null })

    await userEvent.click(screen.getByRole('button', { name: /send/i }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByRole('alert').textContent).toMatch(/which mile/i)
  })

  it('refuses a negative mile instead of clamping it to zero', async () => {
    const onSubmit = shown({ hereMile: null })

    await userEvent.type(screen.getByLabelText(/shut from mile/i), '-12')
    await userEvent.click(screen.getByRole('button', { name: /send/i }))

    // Clamping would file mi 0 - a real place, confidently wrong, and
    // indistinguishable downstream from somebody reporting Springer.
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('says filing this does not close the trail on anyone else’s map', () => {
    shown()

    expect(screen.getByRole('note').textContent).toMatch(
      /does not close the trail on anyone else/i,
    )
    expect(screen.getByRole('note').textContent).toMatch(/moderator reads it first/i)
  })

  it('says the far end may be left empty, in those words', () => {
    shown()

    expect(
      screen.getByText(/leave this empty if you cannot see where it ends/i),
    ).toBeTruthy()
    expect(screen.getByText(/a guessed mile gets drawn as a real one/i)).toBeTruthy()
  })

  it('carries the reason and the note, and stamps the authoring time', async () => {
    const onSubmit = shown()

    await userEvent.click(screen.getByRole('radio', { name: /flooding/i }))
    await userEvent.type(
      screen.getByLabelText(/what did you see/i),
      '  ford is chest deep  ',
    )
    await userEvent.click(screen.getByRole('button', { name: /send/i }))

    const submission = onSubmit.mock.calls[0][0]
    expect(submission.reason).toBe('flooding')
    expect(submission.note).toBe('ford is chest deep')
    // Taken at mount: somebody can start this, walk to the sign to read it,
    // and finish five minutes later. When they SAW it is what matters.
    expect(submission.authoredAt.toISOString()).toBe('2026-08-21T14:00:00.000Z')
  })

  it('says the report will wait when there is no signal', () => {
    shown({ online: false })

    expect(screen.getByRole('button', { name: /save to outbox/i })).toBeTruthy()
    expect(screen.getByRole('status').textContent).toMatch(/wait in your outbox/i)
  })
})
