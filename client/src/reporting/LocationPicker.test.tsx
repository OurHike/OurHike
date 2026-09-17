import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { LocationPicker, type LocationPickerProps } from './LocationPicker'
import {
  AT_THE_FIX,
  STALE_FIX_SECONDS,
  type FixSnapshot,
  type NearbyPlace,
} from '../lib/reportLocation'

afterEach(() => {
  cleanup()
})

// The shared picker (#1563). What it must get right, in the order it would
// hurt somebody if it broke:
//
//   - a named place is offered first and chosen whole, coordinates included
//   - the fix row prints the radius and the age, and is absent with no fix
//   - the map row is absent when the shell offers no map (D10)
//   - the words field appears only when nothing else can place the report
//   - it never counts the places it offers

const NOW = new Date('2026-09-17T14:00:00Z')

const FIX: FixSnapshot = {
  lat: 37.35,
  lon: -80.35,
  mile: 628.4,
  accuracyM: 5,
  fixedAt: new Date('2026-09-17T13:59:40Z'),
}

const PLACES: NearbyPlace[] = [
  {
    id: 'p-near',
    name: 'Niday Shelter',
    type: 'shelter',
    mile: 627.8,
    lat: 37.3,
    lon: -80.3,
    awayMiles: 0.6,
  },
  {
    id: 'p-mid',
    name: 'Craig Creek',
    type: 'water',
    mile: 624.0,
    lat: 37.35,
    lon: -80.35,
    awayMiles: 1.2,
  },
  {
    id: 'p-far',
    name: 'Sarver Hollow Shelter',
    type: 'shelter',
    lat: 37.4,
    lon: -80.4,
    awayMiles: 4.4,
  },
]

function setup(overrides: Partial<LocationPickerProps> = {}) {
  const props: LocationPickerProps = {
    choice: AT_THE_FIX,
    fix: FIX,
    places: PLACES,
    units: 'imperial',
    knowsTrail: true,
    onChoose: vi.fn(),
    now: NOW,
    ...overrides,
  }
  return { props, ...render(<LocationPicker {...props} />) }
}

describe('a named place first', () => {
  it('lists the places in the order given, each with how far away and its mile', () => {
    setup()

    const rows = screen.getAllByRole('button', { pressed: false })
    expect(rows[0]).toHaveTextContent('Niday Shelter')
    expect(rows[0]).toHaveTextContent('0.6 mi away · mi 627.8')
    expect(rows[1]).toHaveTextContent('Craig Creek')
    // No mile on this one, so no marker is invented for it.
    expect(screen.getByTestId('location-place-p-far')).toHaveTextContent('4.4 mi away')
    expect(screen.getByTestId('location-place-p-far')).not.toHaveTextContent(/mi \d/)
  })

  it('writes the distance as a distance in the units the hiker chose - never the marker converted', () => {
    // #986's distinction: 0.6 mi is "970 m" for a metric hiker, while the
    // marker beside it stays "mi 627.8" - a position on this trail.
    setup({ units: 'metric' })

    const row = screen.getByTestId('location-place-p-near')
    expect(row).toHaveTextContent('970 m away')
    expect(row).toHaveTextContent('mi 627.8')
    expect(row).not.toHaveTextContent('1,010')
  })

  it('chooses the whole place - id, name, coordinates and mile - on a tap', () => {
    const { props } = setup()

    fireEvent.click(screen.getByTestId('location-place-p-mid'))

    expect(props.onChoose).toHaveBeenCalledWith({
      kind: 'poi',
      poiId: 'p-mid',
      name: 'Craig Creek',
      lat: 37.35,
      lon: -80.35,
      mile: 624.0,
    })
  })

  it('marks the chosen place pressed, and nothing else', () => {
    setup({
      choice: {
        kind: 'poi',
        poiId: 'p-mid',
        name: 'Craig Creek',
        lat: 37.35,
        lon: -80.35,
      },
    })

    expect(screen.getByTestId('location-place-p-mid')).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByTestId('location-place-p-near')).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    expect(screen.getByTestId('location-fix')).toHaveAttribute('aria-pressed', 'false')
  })

  it('draws no places section with nothing to offer and no search', () => {
    setup({ places: [] })

    expect(screen.queryByRole('heading', { name: 'A named place' })).toBeNull()
  })

  it('searches by name through the shell when asked, and says so when nothing matches', () => {
    const onSearch = vi.fn((query: string) =>
      query === 'katahdin' ? [] : [PLACES[1] as NearbyPlace],
    )
    setup({ places: [], onSearch })

    fireEvent.change(screen.getByTestId('location-search'), {
      target: { value: 'craig' },
    })
    expect(onSearch).toHaveBeenCalledWith('craig')
    expect(screen.getByTestId('location-place-p-mid')).toBeInTheDocument()

    fireEvent.change(screen.getByTestId('location-search'), {
      target: { value: 'katahdin' },
    })
    expect(screen.getByText('Nothing by that name on this phone.')).toBeInTheDocument()
  })

  it('offers a plain filter only past six places when there is no search', () => {
    const many = Array.from({ length: 7 }, (_, index) => ({
      ...PLACES[0],
      id: `p-${index}`,
      name: `Place ${index}`,
    })) as NearbyPlace[]

    const { unmount } = setup({ places: many.slice(0, 6) })
    expect(screen.queryByTestId('location-search')).toBeNull()
    unmount()

    setup({ places: many })
    fireEvent.change(screen.getByTestId('location-search'), {
      target: { value: 'Place 3' },
    })
    expect(screen.getByTestId('location-place-p-3')).toBeInTheDocument()
    expect(screen.queryByTestId('location-place-p-0')).toBeNull()
  })

  it('never counts the places, or says what was skipped', () => {
    setup()

    const picker = screen.getByTestId('location-picker')
    expect(picker.textContent).not.toMatch(
      /\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(more|others?|places?|shown|of)\b/i,
    )
    expect(picker.textContent).not.toMatch(/\b(others?|all|total|showing)\b/i)
  })
})

describe('where you are', () => {
  it('prints the radius in the chosen units and the age of the fix', () => {
    setup()

    expect(screen.getByTestId('location-fix')).toHaveTextContent('±16 ft · just now')

    cleanup()
    setup({ units: 'metric' })
    expect(screen.getByTestId('location-fix')).toHaveTextContent('±5 m · just now')
  })

  it('says the hiker may have moved when the fix is older than STALE_FIX_SECONDS', () => {
    setup({
      fix: { ...FIX, fixedAt: new Date(NOW.getTime() - (STALE_FIX_SECONDS + 30) * 1000) },
    })

    expect(screen.getByTestId('location-fix')).toHaveTextContent(
      'you may have moved since',
    )
  })

  it('is not drawn at all without a fix - never a dead row', () => {
    setup({ fix: null })

    expect(screen.queryByTestId('location-fix')).toBeNull()
  })

  it('chooses the live fix, not a copy of it', () => {
    const { props } = setup({
      choice: { kind: 'point', lat: 1, lon: 1 },
    })

    fireEvent.click(screen.getByTestId('location-fix'))

    // `{ kind: 'fix' }` and nothing else: the coordinates are resolved when
    // the report files, so a hiker who walks on before tapping a tile is
    // filed where they end up, not where they were when they opened this.
    expect(props.onChoose).toHaveBeenCalledWith({ kind: 'fix' })
  })
})

describe('the map, and words', () => {
  it('draws the map row only when the shell offers a map to aim at', () => {
    const { unmount } = setup()
    expect(screen.queryByTestId('location-map')).toBeNull()
    unmount()

    const onPointOnMap = vi.fn()
    setup({ onPointOnMap })
    fireEvent.click(screen.getByTestId('location-map'))
    expect(onPointOnMap).toHaveBeenCalled()
  })

  it('names the marked spot on the map row once one is kept', () => {
    setup({ onPointOnMap: vi.fn(), choice: { kind: 'point', lat: 1, lon: 1, mile: 630 } })

    expect(screen.getByTestId('location-map')).toHaveTextContent('mi 630.0')
    expect(screen.getByTestId('location-map')).toHaveAttribute('aria-pressed', 'true')
  })

  it('asks for words only when nothing else can place the report', () => {
    const words = { value: '', onChange: vi.fn() }

    const { unmount } = setup({ words })
    expect(screen.queryByTestId('location-words')).toBeNull()
    unmount()

    setup({ words, fix: null })
    fireEvent.change(screen.getByTestId('location-words'), {
      target: { value: 'north of the gap' },
    })
    expect(words.onChange).toHaveBeenCalledWith('north of the gap')
    expect(screen.getByText(/nobody turns it into a pin/)).toBeInTheDocument()
  })

  it('leads with why it opened when the report has no place yet', () => {
    setup({ needed: true, fix: null })

    expect(screen.getByRole('alert')).toHaveTextContent('Say where this is first')
  })
})
