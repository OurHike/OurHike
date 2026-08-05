import { describe, it, expect, vi } from 'vitest'
import {
  createDemRequestHandler,
  WorkerDemManager,
  type DemManagerLike,
  type DemRequest,
  type DemResponse,
  type WorkerLike,
} from './demRpc'

// Both protocol ends wired directly to each other - no thread, no jsdom
// Worker gap. What a real page adds is only the postMessage boundary, and
// structured cloning of Blobs, typed arrays and ArrayBuffers is the
// platform's contract, not this module's.
function wire(manager: DemManagerLike): {
  manager: WorkerDemManager
  requests: DemRequest[]
} {
  const requests: DemRequest[] = []
  let deliver: (event: MessageEvent) => void = () => {}

  const handler = createDemRequestHandler(manager, (message: DemResponse) => {
    deliver({ data: message } as MessageEvent)
  })

  const worker: WorkerLike = {
    postMessage(message: DemRequest) {
      requests.push(message)
      handler(message)
    },
    addEventListener(_type, listener) {
      deliver = listener
    },
  }

  return { manager: new WorkerDemManager(worker), requests }
}

function stubManager(overrides: Partial<DemManagerLike> = {}): DemManagerLike {
  return {
    loaded: Promise.resolve(),
    fetchTile: vi.fn().mockResolvedValue({
      data: new Blob([new Uint8Array([7])]),
      cacheControl: 'max-age=60',
    }),
    fetchAndParseTile: vi.fn().mockResolvedValue({
      width: 256,
      height: 256,
      data: new Float32Array([1.5, 2.5]),
    }),
    fetchContourTile: vi.fn().mockResolvedValue({
      arrayBuffer: new Uint8Array([3, 4]).buffer,
    }),
    ...overrides,
  }
}

describe('the DEM worker protocol (#187)', () => {
  it('round-trips a raw tile, bytes and caching headers intact', async () => {
    const stub = stubManager()
    const { manager } = wire(stub)

    const tile = await manager.fetchTile(12, 1198, 1540, new AbortController())

    expect(new Uint8Array(await tile.data.arrayBuffer())).toEqual(new Uint8Array([7]))
    expect(tile.cacheControl).toBe('max-age=60')
    expect(stub.fetchTile).toHaveBeenCalledWith(
      12,
      1198,
      1540,
      expect.any(AbortController),
    )
  })

  it('round-trips a parsed tile as width, height and elevations', async () => {
    const { manager } = wire(stubManager())

    const tile = await manager.fetchAndParseTile(10, 1, 2, new AbortController())

    expect(tile).toMatchObject({ width: 256, height: 256 })
    expect(Array.from(tile.data)).toEqual([1.5, 2.5])
  })

  it('round-trips a contour tile, carrying the options through untouched', async () => {
    const stub = stubManager()
    const { manager } = wire(stub)
    const options = { multiplier: 3.28084, levels: [40, 200] }

    const tile = await manager.fetchContourTile(14, 5, 6, options, new AbortController())

    expect(new Uint8Array(tile.arrayBuffer)).toEqual(new Uint8Array([3, 4]))
    expect(stub.fetchContourTile).toHaveBeenCalledWith(
      14,
      5,
      6,
      options,
      expect.any(AbortController),
    )
  })

  it('marshals a worker-side failure back as a rejection with its message', async () => {
    const { manager } = wire(
      stubManager({
        fetchTile: vi.fn().mockRejectedValue(new Error('DEM tile 1/2/3: HTTP 503')),
      }),
    )

    await expect(manager.fetchTile(1, 2, 3, new AbortController())).rejects.toThrow(
      'DEM tile 1/2/3: HTTP 503',
    )
  })

  it('keeps concurrent requests apart by id', async () => {
    const stub = stubManager({
      fetchTile: vi
        .fn()
        .mockImplementation((z: number) =>
          Promise.resolve({ data: new Blob([new Uint8Array([z])]) }),
        ),
    })
    const { manager } = wire(stub)

    const [a, b] = await Promise.all([
      manager.fetchTile(1, 0, 0, new AbortController()),
      manager.fetchTile(2, 0, 0, new AbortController()),
    ])

    expect(new Uint8Array(await a.data.arrayBuffer())).toEqual(new Uint8Array([1]))
    expect(new Uint8Array(await b.data.arrayBuffer())).toEqual(new Uint8Array([2]))
  })

  it('rejects locally on abort and tells the worker to stop the work', async () => {
    // The worker side holds the promise open so the abort arrives while the
    // request is genuinely in flight.
    let release: (tile: { data: Blob }) => void = () => {}
    const workerSideAborts: boolean[] = []
    const stub = stubManager({
      fetchTile: vi.fn().mockImplementation(
        (_z, _x, _y, abortController: AbortController) =>
          new Promise((resolve) => {
            abortController.signal.addEventListener('abort', () =>
              workerSideAborts.push(true),
            )
            release = resolve as never
          }),
      ),
    })
    const { manager, requests } = wire(stub)

    const abortController = new AbortController()
    const pending = manager.fetchTile(3, 4, 5, abortController)
    abortController.abort()

    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    // The abort really crossed the boundary and stopped the work.
    expect(workerSideAborts).toEqual([true])
    expect(requests.some((request) => request.kind === 'abort')).toBe(true)

    // A late worker resolution answers nobody - and must not throw.
    release({ data: new Blob() })
  })

  it('drops a late reply to an aborted request instead of resolving it', async () => {
    let release: (tile: { data: Blob }) => void = () => {}
    const posted: DemResponse[] = []
    const handler = createDemRequestHandler(
      stubManager({
        fetchTile: vi.fn().mockImplementation(
          () =>
            new Promise((resolve) => {
              release = resolve as never
            }),
        ),
      }),
      (message) => posted.push(message),
    )

    handler({ id: 1, kind: 'fetchTile', z: 1, x: 2, y: 3 })
    handler({ id: 1, kind: 'abort' })
    release({ data: new Blob() })
    await Promise.resolve()
    await Promise.resolve()

    expect(posted).toEqual([])
  })
})
