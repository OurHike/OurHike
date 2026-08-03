import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { ErrorBoundary, ScreenFailed } from './ErrorBoundary'

// React's default for a thrown render, effect, or effect CLEANUP is to unmount
// the whole root - not the component that threw. #131 did exactly that: a
// stale removeControl threw during cleanup on every tab switch away from the
// map, and the hiker got a white page with no navigation on it. What was
// reported was "the download tab shows nothing".
//
// So what these test is not "does React catch errors" but the two promises
// this boundary makes: something renders, and there is a way out of it.

function Boom({ explode }: { explode: boolean }): React.ReactNode {
  if (explode) throw new Error('the map fell over')
  return <p>the map</p>
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

/** React logs a caught error itself; silenced so the run stays readable. */
function quiet() {
  vi.spyOn(console, 'error').mockImplementation(() => {})
}

describe('ErrorBoundary', () => {
  it('renders its children when nothing is wrong', () => {
    render(
      <ErrorBoundary fallback={() => <p>fallback</p>}>
        <Boom explode={false} />
      </ErrorBoundary>,
    )

    expect(screen.getByText('the map')).toBeInTheDocument()
  })

  it('shows the fallback instead of unmounting the tree', () => {
    quiet()

    render(
      <ErrorBoundary fallback={() => <p>fallback</p>}>
        <Boom explode={true} />
      </ErrorBoundary>,
    )

    expect(screen.getByText('fallback')).toBeInTheDocument()
  })

  it('keeps whatever the fallback renders alongside it', () => {
    // The load-bearing part. A fallback with no navigation under it is a white
    // screen with words on it - the hiker still cannot reach the map.
    quiet()

    render(
      <ErrorBoundary
        fallback={() => (
          <>
            <p>fallback</p>
            <nav aria-label="Main">tabs</nav>
          </>
        )}
      >
        <Boom explode={true} />
      </ErrorBoundary>,
    )

    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
  })

  it('tries again when the reset key changes, so navigating away and back recovers', async () => {
    quiet()
    const user = userEvent.setup()

    function Harness() {
      const [tab, setTab] = useState('trail')
      return (
        <>
          <button
            onClick={() => setTab((current) => (current === 'trail' ? 'more' : 'trail'))}
          >
            switch
          </button>
          <ErrorBoundary resetKey={tab} fallback={() => <p>fallback</p>}>
            <Boom explode={tab === 'trail'} />
          </ErrorBoundary>
        </>
      )
    }

    render(<Harness />)
    expect(screen.getByText('fallback')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'switch' }))

    expect(screen.getByText('the map')).toBeInTheDocument()
  })

  it('stays on the fallback while the reset key is unchanged', () => {
    // Clearing the error on every update would re-render the subtree that just
    // threw, which throws again - a loop, not a recovery.
    quiet()

    const { rerender } = render(
      <ErrorBoundary resetKey="trail" fallback={() => <p>fallback</p>}>
        <Boom explode={true} />
      </ErrorBoundary>,
    )
    rerender(
      <ErrorBoundary resetKey="trail" fallback={() => <p>fallback</p>}>
        <Boom explode={true} />
      </ErrorBoundary>,
    )

    expect(screen.getByText('fallback')).toBeInTheDocument()
  })

  it('logs the error rather than sending it anywhere', () => {
    // A chosen "no telemetry", not an oversight - there is none in this client
    // and adding some carries its own privacy weight. console is where a
    // developer looks and a hiker never does.
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <ErrorBoundary fallback={() => <p>fallback</p>}>
        <Boom explode={true} />
      </ErrorBoundary>,
    )

    expect(error).toHaveBeenCalled()
  })
})

describe('ScreenFailed', () => {
  it('names what broke rather than saying something went wrong', () => {
    render(<ScreenFailed what="The map" />)

    expect(screen.getByRole('heading')).toHaveTextContent(/the map stopped working/i)
  })

  it('says the rest of the app still works, because it does', () => {
    render(<ScreenFailed what="The map" />)

    expect(screen.getByText(/rest of the app is fine/i)).toBeInTheDocument()
  })

  it('offers no reload, which is the action least likely to help offline', () => {
    render(<ScreenFailed what="The map" />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByText(/reload|refresh/i)).not.toBeInTheDocument()
  })

  it('reassures about the two things a hiker would fear losing', () => {
    render(<ScreenFailed what="The map" />)

    expect(screen.getByText(/downloaded map/i)).toHaveTextContent(/outbox/i)
  })

  it('announces itself, so it is not a silent swap for a screen reader', () => {
    render(<ScreenFailed what="The map" />)

    expect(screen.getByRole('alert')).toBeInTheDocument()
  })
})
