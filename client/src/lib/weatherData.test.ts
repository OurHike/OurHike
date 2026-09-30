import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { resetWeatherReads, useWaypointWeather } from './weatherData'
import {
  weatherAlertsDocument,
  weatherCellDocument,
} from '../../preview-shots/fixtures/weather.mjs'

// How the waypoint card gets NOAA's forecast (#1056 build step 3): the cell
// file for the waypoint's 1° cell and the NWS alerts file, from the bucket
// with signal and from the copy this phone kept without it. The one promise
// worth most here is the negative one - nothing shows until there is a
// forecast for this exact square, so a 404, a square the file does not list
// and a phone with nothing kept all leave the card as it was.

vi.mock('idb-keyval', () => {
  const store = new Map<string, unknown>()
  return {
    get: vi.fn(async (key: string) => store.get(key)),
    set: vi.fn(async (key: string, value: unknown) => void store.set(key, value)),
    del: vi.fn(async (key: string) => void store.delete(key)),
    __clear: () => store.clear(),
  }
})

vi.mock('./config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./config')>()),
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.test/${key}`,
}))

const HUT = { lon: -71.319, lat: 44.2587 }
const SQUARE: [number, number] = [563, 2073]
const CYCLE = new Date('2026-09-30T08:00Z')

function respond(routes: Record<string, unknown>) {
  const fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    const key = Object.keys(routes).find((path) => url.endsWith(path))
    if (key === undefined) return new Response('not found', { status: 404 })
    return new Response(JSON.stringify(routes[key]), { status: 200 })
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

function setOnline(online: boolean) {
  Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => online })
}

beforeEach(() => {
  resetWeatherReads()
  setOnline(true)
})

afterEach(async () => {
  vi.unstubAllGlobals()
  const store = (await import('idb-keyval')) as unknown as { __clear(): void }
  store.__clear()
})

const ROUTES = {
  'conditions/weather/n44w072.json': weatherCellDocument({
    cycle: CYCLE,
    squares: [SQUARE],
  }),
  'conditions/weather_alerts.json': weatherAlertsDocument({
    fetchedAt: new Date('2026-09-30T08:52Z'),
  }),
}

describe('useWaypointWeather', () => {
  it("asks for the waypoint's own cell file, n44w072 for Lakes of the Clouds, and finds its square", async () => {
    const fetch = respond(ROUTES)
    const { result } = renderHook(() => useWaypointWeather(HUT.lon, HUT.lat))

    await waitFor(() => expect(result.current.kind).toBe('forecast'))
    expect(fetch).toHaveBeenCalledWith(
      'https://data.test/conditions/weather/n44w072.json',
    )
    if (result.current.kind !== 'forecast') return
    expect(result.current.square).toEqual(SQUARE)
    expect(result.current.live).toBe(true)
    expect(result.current.alerts?.value.fetchedAt.toISOString()).toBe(
      '2026-09-30T08:52:00.000Z',
    )
  })

  it('shows nothing when the cell file 404s - which is every read in production until weather is promoted', async () => {
    const fetch = respond({})
    const { result } = renderHook(() => useWaypointWeather(HUT.lon, HUT.lat))

    await waitFor(() => expect(fetch).toHaveBeenCalled())
    await act(async () => {})
    expect(result.current.kind).toBe('none')
  })

  it('shows nothing for a waypoint whose square the file does not list', async () => {
    respond({
      ...ROUTES,
      'conditions/weather/n44w072.json': weatherCellDocument({
        cycle: CYCLE,
        squares: [[563, 2074]],
      }),
    })
    const { result } = renderHook(() => useWaypointWeather(HUT.lon, HUT.lat))

    await act(async () => {})
    await act(async () => {})
    expect(result.current.kind).toBe('none')
  })

  it('never asks for a waypoint off the CONUS grid, Anchorage here', async () => {
    const fetch = respond(ROUTES)
    const { result } = renderHook(() => useWaypointWeather(-149.9, 61.2))

    await act(async () => {})
    expect(fetch).not.toHaveBeenCalled()
    expect(result.current.kind).toBe('none')
  })

  it('falls back to the copy it kept when the phone has no signal, and says it is not live', async () => {
    respond(ROUTES)
    const first = renderHook(() => useWaypointWeather(HUT.lon, HUT.lat))
    await waitFor(() => expect(first.result.current.kind).toBe('forecast'))
    first.unmount()

    resetWeatherReads()
    setOnline(false)
    const fetch = respond({})
    const { result } = renderHook(() => useWaypointWeather(HUT.lon, HUT.lat))

    await waitFor(() => expect(result.current.kind).toBe('forecast'))
    expect(fetch).not.toHaveBeenCalled()
    if (result.current.kind !== 'forecast') return
    expect(result.current.live).toBe(false)
    expect(result.current.alerts?.live).toBe(false)
  })

  it('reuses one live read for the next card in the same cell rather than fetching it again', async () => {
    const fetch = respond(ROUTES)
    const first = renderHook(() => useWaypointWeather(HUT.lon, HUT.lat))
    await waitFor(() => expect(first.result.current.kind).toBe('forecast'))
    const second = renderHook(() => useWaypointWeather(HUT.lon, HUT.lat))
    await waitFor(() => expect(second.result.current.kind).toBe('forecast'))

    const cellReads = fetch.mock.calls.filter(([url]) =>
      String(url).includes('weather/n44w072'),
    )
    expect(cellReads).toHaveLength(1)
  })
})
