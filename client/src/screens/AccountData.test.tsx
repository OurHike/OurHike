import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AccountDataSettings } from './Settings'
import type { DeletionReceipt } from '../lib/api'

// Taking the data back, and leaving (#895, ACCOUNT_SYNC.md phase E).
//
// Like #894's tests, most of this is about SENTENCES, and for a sharper
// reason: this screen is the only place a hiker learns two things they would
// be entitled to be angry about discovering afterwards - that the
// contributions other people rely on do not go, and that a photograph they
// shared keeps their trail name because the licence it was granted under
// requires the credit and no deletion can walk that back.
//
// The issue is explicit that those have to be said "plainly before the button
// is pressed, not in a policy nobody reads", so the tests that matter most are
// the ones asserting they are on screen at the moment of the confirm - and
// that the destructive button is not reachable in one press.

function receipt(over: Partial<DeletionReceipt> = {}): DeletionReceipt {
  return {
    trips_deleted: 4,
    planned_hikes_deleted: 1,
    hikes_deleted: 1,
    preferences_deleted: 1,
    assignments_released: 0,
    hours_deleted: 0,
    app_failure_reports_unlinked: 0,
    kept: {},
    ...over,
  }
}

function show(
  onExport = vi.fn().mockResolvedValue(undefined),
  onDelete = vi.fn().mockResolvedValue(receipt()),
) {
  render(<AccountDataSettings onExport={onExport} onDelete={onDelete} />)
  return { onExport, onDelete }
}

afterEach(cleanup)

describe('taking your data', () => {
  it('offers the file from the same screen as the deletion', () => {
    show()

    expect(
      screen.getByRole('button', { name: /download everything of yours/i }),
    ).toBeTruthy()
    expect(screen.getByRole('button', { name: /delete my account/i })).toBeTruthy()
  })

  it('builds the file when asked', async () => {
    const { onExport } = show()

    await userEvent.click(
      screen.getByRole('button', { name: /download everything of yours/i }),
    )

    expect(onExport).toHaveBeenCalledTimes(1)
  })

  it('says the photographs are not in it', () => {
    // The archive lists every photo and carries none of their bytes, because
    // a signed R2 link lives five minutes. A hiker who opens the file looking
    // for their pictures should have been told here rather than there.
    show()

    expect(screen.getByText(/photographs themselves are not in it/i)).toBeTruthy()
  })
})

describe('the confirm step', () => {
  it('does not delete on the first press', async () => {
    const { onDelete } = show()

    await userEvent.click(screen.getByRole('button', { name: /^delete my account$/i }))

    expect(onDelete).not.toHaveBeenCalled()
  })

  it('says what stays, before the button that deletes', async () => {
    show()

    await userEvent.click(screen.getByRole('button', { name: /^delete my account$/i }))

    expect(screen.getByText(/other hikers are routing around them/i)).toBeTruthy()
    expect(screen.getByText(/volunteer hours a club has already confirmed/i)).toBeTruthy()
    // And only now is the destructive control on screen at all.
    expect(screen.getByRole('button', { name: /yes, delete my account/i })).toBeTruthy()
  })

  it('says a shared photo keeps the trail name, and why', async () => {
    // The single most surprising consequence, and the one this app cannot
    // undo for them afterwards.
    show()

    await userEvent.click(screen.getByRole('button', { name: /^delete my account$/i }))

    expect(screen.getByText(/keep your trail name/i)).toBeTruthy()
    expect(screen.getByText(/licence that requires the credit/i)).toBeTruthy()
  })

  it('says this phone keeps its own copy', async () => {
    // Deleting the account does not wipe IndexedDB, deliberately. A hiker
    // who wanted to be rid of everything needs to know the app is still
    // holding their trips.
    show()

    await userEvent.click(screen.getByRole('button', { name: /^delete my account$/i }))

    expect(screen.getByText(/delete the app to be rid of that too/i)).toBeTruthy()
  })

  it('lets a hiker back out', async () => {
    const { onDelete } = show()

    await userEvent.click(screen.getByRole('button', { name: /^delete my account$/i }))
    await userEvent.click(screen.getByRole('button', { name: /keep my account/i }))

    expect(onDelete).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: /yes, delete my account/i })).toBeNull()
  })
})

describe('after the deletion', () => {
  it('names what stayed, against the real rows', async () => {
    // The screen's version was a promise; the receipt is a fact, and the
    // words are keyed the same on both sides so they cannot drift into
    // describing different things.
    const { onDelete } = show(
      undefined,
      vi
        .fn()
        .mockResolvedValue(
          receipt({ kept: { 'photos you shared': 2, 'condition reports': 5 } }),
        ),
    )

    await userEvent.click(screen.getByRole('button', { name: /^delete my account$/i }))
    await userEvent.click(screen.getByRole('button', { name: /yes, delete my account/i }))

    expect(onDelete).toHaveBeenCalledTimes(1)
    expect(await screen.findByText(/2 photos you shared/i)).toBeTruthy()
    expect(screen.getByText(/5 condition reports/i)).toBeTruthy()
  })

  it('does not print a list for somebody who contributed nothing', async () => {
    show()

    await userEvent.click(screen.getByRole('button', { name: /^delete my account$/i }))
    await userEvent.click(screen.getByRole('button', { name: /yes, delete my account/i }))

    expect(await screen.findByText(/your account is gone/i)).toBeTruthy()
    expect(screen.queryByText(/what stayed, as promised/i)).toBeNull()
  })

  it('offers no way to press it again', async () => {
    // The account is gone; a second press would 401. Removing the control
    // is the honest surface for that rather than an error a hiker earned by
    // pressing a button we left there.
    show()

    await userEvent.click(screen.getByRole('button', { name: /^delete my account$/i }))
    await userEvent.click(screen.getByRole('button', { name: /yes, delete my account/i }))

    await screen.findByText(/your account is gone/i)
    expect(screen.queryByRole('button', { name: /delete my account/i })).toBeNull()
  })
})

describe('when it fails', () => {
  it('says nothing was changed, and leaves the button there', async () => {
    const onDelete = vi.fn().mockRejectedValue(new Error('the network went away'))
    show(undefined, onDelete)

    await userEvent.click(screen.getByRole('button', { name: /^delete my account$/i }))
    await userEvent.click(screen.getByRole('button', { name: /yes, delete my account/i }))

    expect(await screen.findByText(/nothing was changed/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: /yes, delete my account/i })).toBeTruthy()
  })

  it('still says what stays, so the second press is as informed as the first', async () => {
    const onDelete = vi.fn().mockRejectedValue(new Error('the network went away'))
    show(undefined, onDelete)

    await userEvent.click(screen.getByRole('button', { name: /^delete my account$/i }))
    await userEvent.click(screen.getByRole('button', { name: /yes, delete my account/i }))
    await screen.findByText(/nothing was changed/i)

    expect(screen.getByText(/keep your trail name/i)).toBeTruthy()
  })

  it('an unreadable phone is said out loud rather than left as a dead button', async () => {
    // The failure this catches is the one #891 shipped and had to fix: a
    // rejection nobody catches is QUIETER than a log while reading like the
    // error was taken seriously. Here it would leave a hiker pressing a
    // button that does nothing and being told nothing.
    const onExport = vi.fn().mockRejectedValue(new Error('unreadable'))
    show(onExport)

    await userEvent.click(
      screen.getByRole('button', { name: /download everything of yours/i }),
    )

    expect(await screen.findByText(/could not be read/i)).toBeTruthy()
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /download everything of yours/i }),
      ).toBeTruthy(),
    )
  })
})
