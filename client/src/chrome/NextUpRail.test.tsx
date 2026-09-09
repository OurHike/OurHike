import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { NextUpRail, RAIL_MAX_CARDS, railHeading } from './NextUpRail'

// The rail inherits the lanes' contract (#527, WIREFRAMES.md §11) in a new
// shape: every card is a real control opening the same waypoint card a map
// pin does, an unknown type still gets a card, staleness words ride only
// where the pixels do, and the heading never claims a direction nobody has.

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const POINTS = [
  { id: 'w1', type: 'water', mile: 1402, name: 'Sartain Spring' },
  { id: 's1', type: 'shelter', mile: 1406, name: 'Bailey Gap Shelter' },
  { id: 'b1', type: 'water', mile: 1399, name: 'Behind Spring' },
]

function props(overrides = {}) {
  return {
    points: POINTS,
    subject: 'ahead' as const,
    currentMile: 1400.5,
    direction: 'NOBO' as const,
    onSelectPoi: vi.fn(),
    ...overrides,
  }
}

describe('NextUpRail', () => {
  it('walks ahead in the settled direction, nearest first', () => {
    render(<NextUpRail {...props()} />)

    const names = [...document.querySelectorAll('.next-up__card-name')].map(
      (name) => name.textContent,
    )
    // The spring behind the hiker is the map's business, not the rail's.
    expect(names).toEqual(['Sartain Spring', 'Bailey Gap Shelter'])
  })

  it('walks the other way for a southbounder', () => {
    render(<NextUpRail {...props({ direction: 'SOBO' })} />)

    const names = [...document.querySelectorAll('.next-up__card-name')].map(
      (name) => name.textContent,
    )
    expect(names).toEqual(['Behind Spring'])
  })

  it('opens a card through the one shared handler', async () => {
    const onSelectPoi = vi.fn()
    const user = userEvent.setup()
    render(<NextUpRail {...props({ onSelectPoi })} />)

    await user.click(screen.getByRole('button', { name: /sartain spring/i }))

    expect(onSelectPoi).toHaveBeenCalledWith('w1')
  })

  it('says how far each card is, in the meta a signpost would carry', () => {
    render(<NextUpRail {...props()} />)

    expect(screen.getByText('water · 1.5 mi')).toBeInTheDocument()
    expect(screen.getByText('shelter · 5.5 mi')).toBeInTheDocument()
  })

  it('falls back to the mile itself when nothing knows where the hiker is', () => {
    render(<NextUpRail {...props({ currentMile: null, direction: undefined })} />)

    expect(screen.getByText('water · mi 1,402.0')).toBeInTheDocument()
  })

  it('gives an unknown waypoint type a card rather than dropping it', () => {
    // The pipeline can publish a type this build has never heard of; hiding
    // it behind a client release would hide a real thing on the trail - the
    // lanes' own rule, kept.
    render(
      <NextUpRail {...props({ points: [{ id: 'y1', type: 'yurt', mile: 1401 }] })} />,
    )

    expect(screen.getByRole('button', { name: /yurt/i })).toBeInTheDocument()
  })

  it('lets the staleness words ride only where the pixels do', () => {
    render(
      <NextUpRail
        {...props({
          stalenessFor: (id: string) =>
            id === 'w1'
              ? {
                  treatment: {
                    ring: 'green' as const,
                    opacity: 1,
                    borderStyle: 'solid' as const,
                  },
                  words: 'Confirmed recently',
                }
              : {
                  treatment: {
                    ring: 'none' as const,
                    opacity: 1,
                    borderStyle: 'solid' as const,
                  },
                  words: 'Never confirmed',
                },
        })}
      />,
    )

    expect(
      screen.getByRole('button', { name: /sartain spring — confirmed recently/i }),
    ).toBeInTheDocument()
    // The neutral shelter names itself and stays quiet.
    expect(screen.getByRole('button', { name: 'Bailey Gap Shelter' })).toBeInTheDocument()
  })

  it('says when the rail was cut, so a short rail never reads as a short trail', () => {
    const many = Array.from({ length: RAIL_MAX_CARDS + 6 }, (_, i) => ({
      id: `m${i}`,
      type: 'water',
      mile: 1401 + i * 0.1,
      name: `Spring ${i}`,
    }))
    render(<NextUpRail {...props({ points: many })} />)

    expect(screen.getByText(`${RAIL_MAX_CARDS} of ${many.length}`)).toBeInTheDocument()
  })

  it('never claims NEXT UP without a settled direction', () => {
    expect(railHeading('ahead', undefined)).toBe('NEARBY')
    expect(railHeading('ahead', 'NOBO')).toBe('NEXT UP')
    expect(railHeading('planned-stretch', 'NOBO')).toBe('ON THIS STRETCH')
    expect(railHeading('map-view', undefined)).toBe('IN VIEW')
    expect(railHeading('whole-trail', 'SOBO')).toBe('ON THE TRAIL')
  })
})
