import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen } from '@testing-library/react'
import { ErrorBoundary } from '../chrome/ErrorBoundary'
import { deferredScreen } from './deferredScreen'

function Greeting({ name }: { name: string }) {
  return <p>Hello, {name}</p>
}

/** A module load the test releases by hand. */
function heldLoad<T>(value: T) {
  let release: (() => void) | null = null
  let fail: ((error: Error) => void) | null = null
  let asked = 0
  const load = () => {
    asked += 1
    return new Promise<T>((resolve, reject) => {
      release = () => resolve(value)
      fail = reject
    })
  }
  return {
    load,
    release: () => release?.(),
    fail: (error: Error) => fail?.(error),
    get asked() {
      return asked
    },
  }
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('a deferred screen', () => {
  it('renders nothing until its module lands, then the module', async () => {
    const held = heldLoad(Greeting)
    const Deferred = deferredScreen(held.load, 'Greeting')

    const { container } = render(<Deferred name="Ridge" />)
    expect(container).toBeEmptyDOMElement()

    await act(async () => {
      held.release()
    })
    expect(screen.getByText('Hello, Ridge')).toBeInTheDocument()
  })

  it('renders synchronously once preloaded - no empty frame, exactly like a static import', async () => {
    const held = heldLoad(Greeting)
    const Deferred = deferredScreen(held.load, 'Greeting')
    const preloading = Deferred.preload()
    held.release()
    await preloading

    const { container } = render(<Deferred name="Ridge" />)

    expect(container).not.toBeEmptyDOMElement()
    expect(screen.getByText('Hello, Ridge')).toBeInTheDocument()
  })

  it('loads the module once, however many times it is asked for', async () => {
    const held = heldLoad(Greeting)
    const Deferred = deferredScreen(held.load, 'Greeting')

    void Deferred.preload()
    void Deferred.preload()
    render(<Deferred name="A" />)
    render(<Deferred name="B" />)
    await act(async () => {
      held.release()
    })

    expect(held.asked).toBe(1)
    expect(screen.getByText('Hello, A')).toBeInTheDocument()
    expect(screen.getByText('Hello, B')).toBeInTheDocument()
  })

  it('hands a chunk that never comes to the nearest error boundary, and tries again next time', async () => {
    const held = heldLoad(Greeting)
    const Deferred = deferredScreen(held.load, 'Greeting')

    vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <ErrorBoundary fallback={() => <p>The screen failed</p>}>
        <Deferred name="Ridge" />
      </ErrorBoundary>,
    )
    await act(async () => {
      held.fail(new Error('ChunkLoadError'))
    })
    expect(screen.getByText('The screen failed')).toBeInTheDocument()

    // The failed import is forgotten: a fresh mount asks again.
    const second = heldLoad(Greeting)
    const Again = deferredScreen(second.load, 'Greeting')
    render(<Again name="Ridge" />)
    await act(async () => {
      second.release()
    })
    expect(held.asked).toBe(1)
    expect(second.asked).toBe(1)
    expect(screen.getByText('Hello, Ridge')).toBeInTheDocument()
  })
})
