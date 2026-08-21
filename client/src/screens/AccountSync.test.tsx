import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AccountSyncSettings } from './Settings'
import type { SyncStatus } from '../lib/syncStatus'

// What a hiker is told about their own sync (#894, ACCOUNT_SYNC.md phase D).
//
// Almost every test here is about a SENTENCE rather than about a control,
// which is right for this screen: the machinery works whether or not the
// copy is honest, and the copy is the whole feature. Two of them are the
// ones that would matter most if they broke.
//
//   - "stop" must never read as "delete". Someone who suspects the button
//     might discard their trips will not press it, and someone who presses
//     it expecting a delete has been misled.
//   - a phone holding trips the account has never seen must not read as
//     safe. That is exactly the impression silence already gives, so a
//     screen reproducing it has bought nothing.

const NOW = new Date('2026-08-21T12:00:00Z')

function status(over: Partial<SyncStatus> = {}): SyncStatus {
  return {
    lastSyncedAt: new Date('2026-08-21T09:00:00Z'),
    neverSent: [],
    unsentEdits: [],
    preferencesUnsent: false,
    hikeUnsent: false,
    ...over,
  }
}

function show(over: Partial<SyncStatus> = {}, enabled = true, onToggle = vi.fn()) {
  render(
    <AccountSyncSettings
      status={status(over)}
      enabled={enabled}
      onToggle={onToggle}
      now={NOW}
    />,
  )
  return onToggle
}

afterEach(cleanup)

describe('when the account last heard from this phone', () => {
  it('gives a real age rather than a spinner', () => {
    show()

    expect(screen.getByText('3h ago')).toBeInTheDocument()
  })

  it('says so plainly on a phone that has never sent anything', () => {
    show({ lastSyncedAt: null })

    expect(screen.getByText('never synced')).toBeInTheDocument()
  })

  it('does not borrow the conditions bucket’s heading', () => {
    // "Your data" already has a "Last synced" row, and it is a different
    // clock - the published bucket every hiker gets with or without an
    // account. Two rows reading as one number is the confusion this whole
    // section exists to avoid.
    show()

    expect(screen.queryByText('Last synced')).not.toBeInTheDocument()
    expect(screen.getByText('Last sent')).toBeInTheDocument()
  })
})

describe('what is on this phone only', () => {
  it('names the trips, rather than counting them', () => {
    show({ neverSent: ['Grayson Highlands', 'Roan Mountain'] })

    expect(screen.getByText('Grayson Highlands')).toBeInTheDocument()
    expect(screen.getByText('Roan Mountain')).toBeInTheDocument()
    expect(screen.queryByText(/2 items/i)).not.toBeInTheDocument()
  })

  it('says what losing the phone would cost', () => {
    show({ neverSent: ['Grayson Highlands'] })

    expect(screen.getByText(/if you lost it today/i)).toBeInTheDocument()
  })

  it('says something different about a trip the account holds in an older form', () => {
    // The distinction that decides whether losing the phone costs a trip or
    // costs an afternoon. Collapsing the two lists would lose it.
    show({ unsentEdits: ['Grayson Highlands'] })

    expect(screen.getByText(/older copy/i)).toBeInTheDocument()
    expect(screen.queryByText(/if you lost it today/i)).not.toBeInTheDocument()
  })

  it('mentions an unsent hike and unsent settings in their own words', () => {
    show({ hikeUnsent: true, preferencesUnsent: true })

    expect(screen.getByText(/hike you are on has not been sent/i)).toBeInTheDocument()
    expect(screen.getByText(/settings have not been sent/i)).toBeInTheDocument()
  })

  it('says everything is safe only when it is', () => {
    show()

    expect(
      screen.getByText(/everything on this phone has reached your account/i),
    ).toBeInTheDocument()
  })

  it('never says everything is safe over a trip that has never been sent', () => {
    // The failure this screen exists to replace: silence reads as "fine"
    // whether or not it is.
    show({ neverSent: ['Grayson Highlands'] })

    expect(
      screen.queryByText(/everything on this phone has reached/i),
    ).not.toBeInTheDocument()
  })
})

describe('photos', () => {
  it('says they are not built yet, rather than calling them off', () => {
    // The issue asks for "what is off" so a hiker reads it as a state they
    // chose. Nobody chose this - phase C is unbuilt - and calling it "off"
    // would tell them they had made a decision never offered to them.
    show()

    expect(screen.getByText(/not built yet/i)).toBeInTheDocument()
    expect(screen.queryByText(/photo sync is off/i)).not.toBeInTheDocument()
  })
})

describe('stopping', () => {
  it('offers to stop while it is running', () => {
    show()

    expect(screen.getByRole('button', { name: /stop syncing/i })).toBeInTheDocument()
  })

  it('offers to start again once stopped', () => {
    show({}, false)

    expect(screen.getByRole('button', { name: /start syncing/i })).toBeInTheDocument()
  })

  it('never lets "stop" read as "delete"', () => {
    // The load-bearing sentence in this file.
    show()

    const promise = screen.getByText(/does not delete anything, anywhere/i)
    expect(promise).toBeInTheDocument()
    expect(screen.getByText(/only stops sending/i)).toBeInTheDocument()
  })

  it('says nothing is being sent while it is stopped, and that it is all still here', () => {
    show({}, false)

    expect(screen.getByText(/nothing below is being sent/i)).toBeInTheDocument()
    expect(screen.getByText(/everything is still here/i)).toBeInTheDocument()
  })

  it('asks the shell to turn it off', async () => {
    const onToggle = show()

    await userEvent.click(screen.getByRole('button', { name: /stop syncing/i }))

    expect(onToggle).toHaveBeenCalledWith(false)
  })

  it('asks the shell to turn it back on', async () => {
    const onToggle = show({}, false)

    await userEvent.click(screen.getByRole('button', { name: /start syncing/i }))

    expect(onToggle).toHaveBeenCalledWith(true)
  })
})

describe('what it must never do', () => {
  it('draws no progress bar and reports no percentage', () => {
    // HIKE_PLANNING.md's anti-gamification guardrail: this screen reports
    // machinery, never the hiker.
    const { container } = render(
      <AccountSyncSettings
        status={status({ neverSent: ['A', 'B'], unsentEdits: ['C'] })}
        enabled
        onToggle={vi.fn()}
        now={NOW}
      />,
    )

    expect(container.querySelector('progress')).toBeNull()
    expect(container.querySelector('[role="progressbar"]')).toBeNull()
    expect(container.textContent).not.toMatch(/%/)
  })
})
