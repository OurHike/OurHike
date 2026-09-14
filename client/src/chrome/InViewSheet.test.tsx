// In view (#1373, frame 12a): the viewport's waypoints as a list, in trail
// order, with distances only where both miles are known.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { IN_VIEW_ROW_PX, InViewSheet, type InViewSheetProps } from './InViewSheet'

const POINTS = [
  {
    id: 'spring',
    type: 'water',
    lat: 41.2,
    lon: -74.5,
    confidence: 'low' as const,
    name: 'Murray spring',
  },
  {
    id: 'shelter',
    type: 'shelter',
    lat: 41.3,
    lon: -74.5,
    confidence: 'high' as const,
    name: 'Brink Road shelter',
  },
  { id: 'view', type: 'viewpoint', lat: 41.4, lon: -74.5, confidence: 'high' as const },
]

const MILES: Record<string, number> = { spring: 1336.4, shelter: 1318.4 }

const PROPS: InViewSheetProps = {
  open: true,
  points: POINTS,
  total: 23,
  currentMile: 1336.3,
  mileOf: (id) => MILES[id],
  units: 'imperial',
  onSelectPoi: vi.fn(),
  onClose: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('what is in view', () => {
  it('counts against the phone, lists in mile order, and prints a distance only where both miles are known', () => {
    render(<InViewSheet {...PROPS} />)

    expect(screen.getByRole('dialog', { name: 'In view' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'In view · 3 of 23' })).toBeInTheDocument()

    const rows = within(screen.getByRole('list')).getAllByRole('button')
    // The shelter at mi 1,318.4 before the spring at 1,336.4; the point the
    // download cannot place comes last, by name.
    expect(rows[0]).toHaveTextContent('Brink Road shelter')
    expect(rows[0]).toHaveTextContent('shelter · mi 1,318.4 · 17.9 mi away')
    expect(rows[1]).toHaveTextContent('Murray spring')
    expect(rows[1]).toHaveTextContent('water · mi 1,336.4 · 0.1 mi away')
    expect(rows[2]).toHaveTextContent('Viewpoint')
    expect(rows[2]).not.toHaveTextContent(/away|mi \d/)
  })

  it('opens the waypoint a row names, the same card a pin opens', async () => {
    const user = userEvent.setup()
    const onSelectPoi = vi.fn()
    render(<InViewSheet {...PROPS} onSelectPoi={onSelectPoi} />)

    await user.click(screen.getByRole('button', { name: /Murray spring/ }))
    expect(onSelectPoi).toHaveBeenCalledWith('spring')
  })

  it('prints no distance without the hiker’s own mile, and rides staleness words where given', () => {
    render(
      <InViewSheet
        {...PROPS}
        currentMile={null}
        stalenessFor={(id) =>
          id === 'spring'
            ? {
                treatment: { ring: 'amber', faded: false } as never,
                words: 'flowing 3 days ago',
              }
            : null
        }
      />,
    )
    const spring = screen.getByRole('button', { name: /Murray spring/ })
    expect(spring).toHaveTextContent('water · mi 1,336.4 · flowing 3 days ago')
    expect(spring).not.toHaveTextContent(/away/)
  })

  it('counts only what is in view when the shell gives no total, and says what to do with nothing', () => {
    render(<InViewSheet {...PROPS} total={undefined} />)
    expect(screen.getByRole('heading', { name: 'In view · 3' })).toBeInTheDocument()

    cleanup()
    render(<InViewSheet {...PROPS} points={[]} />)
    expect(screen.getByText(/Nothing the map draws is in view/)).toBeInTheDocument()
    expect(screen.queryByText(/signal|online/i)).toBeNull()
  })

  it('lists the workdays in view under the waypoints, with the window to widen (#1373, frame 14d)', async () => {
    const user = userEvent.setup()
    const onChangeWindow = vi.fn()
    const onSelect = vi.fn()
    render(
      <InViewSheet
        {...PROPS}
        workdays={{
          rows: [
            {
              id: 'wd1',
              title: 'Sidehill and drainage, Wawayanda',
              club: 'NYNJTC',
              dates: 'Sep 12',
              awayMi: 8.4,
              capacity: 12,
              contact: 'trails@nynjtc.org',
              lat: 41.2,
              lon: -74.5,
            },
          ],
          window: 'fortnight',
          onChangeWindow,
          onSelect,
        }}
      />,
    )

    const section = screen.getByRole('region', { name: 'Workdays in view' })
    expect(
      within(section).getByRole('heading', { name: 'Workdays in view · 1' }),
    ).toBeInTheDocument()
    const row = within(section).getByRole('button', { name: /Sidehill and drainage/ })
    expect(row).toHaveTextContent('NYNJTC · Sep 12 · 8.4 trail mi away · room for 12')
    await user.click(row)
    expect(onSelect).toHaveBeenCalledWith('wd1')

    const windows = within(section).getByRole('group', { name: 'Show workdays in' })
    expect(within(windows).getByRole('button', { name: 'Next 14 days' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await user.click(within(windows).getByRole('button', { name: 'This weekend' }))
    expect(onChangeWindow).toHaveBeenCalledWith('weekend')
  })

  it('says what to do with no workday in the window, and shows no section with none held', () => {
    render(
      <InViewSheet
        {...PROPS}
        workdays={{
          rows: [],
          window: 'weekend',
          onChangeWindow: vi.fn(),
          onSelect: vi.fn(),
        }}
      />,
    )
    expect(screen.getByText(/No workdays in view in this window/)).toBeInTheDocument()

    cleanup()
    render(<InViewSheet {...PROPS} />)
    expect(screen.queryByRole('region', { name: 'Workdays in view' })).toBeNull()
  })

  // The list is windowed (the maintainer's review of #1374): every row is
  // kept, the ones on screen are mounted, and the rest hold their height.
  it('mounts only the rows a screen holds, with spacers standing in for the rest', () => {
    const many = Array.from({ length: 500 }, (_, i) => ({
      id: `p${i}`,
      type: 'water',
      lat: 41 + i / 1000,
      lon: -74.5,
      confidence: 'high' as const,
      name: `Spring ${i}`,
    }))
    render(<InViewSheet {...PROPS} points={many} total={undefined} mileOf={undefined} />)

    expect(screen.getByRole('heading', { name: 'In view · 500' })).toBeInTheDocument()
    const rows = screen.getAllByRole('button', { name: /^Spring / })
    expect(rows.length).toBeGreaterThan(8)
    expect(rows.length).toBeLessThan(60)
    // The rows say where they sit in the whole, and the spacers hold the
    // height of what is not mounted.
    const list = screen.getByRole('list', { name: '500 waypoints in view' })
    expect(list.querySelector('li[aria-posinset="1"]')).not.toBeNull()
    const spacer = list.querySelector('.in-view__spacer') as HTMLElement
    expect(spacer).not.toBeNull()
    expect(spacer.style.height).toBe(`${(500 - rows.length) * IN_VIEW_ROW_PX}px`)
    expect(list.querySelectorAll('li')).toHaveLength(rows.length + 1)
  })

  it('says when the map is drawing none of the rows, rather than letting "in view" claim a pin', () => {
    render(<InViewSheet {...PROPS} drawnNone />)

    expect(
      screen.getByText(/the map draws none of these at this zoom/i),
    ).toBeInTheDocument()
    // The rows are still listed: the frame holds them, the zoom hides them.
    expect(screen.getByRole('button', { name: /Murray spring/ })).toBeInTheDocument()
  })

  it('renders nothing while closed', () => {
    const { container } = render(<InViewSheet {...PROPS} open={false} />)
    expect(container).toBeEmptyDOMElement()
  })
})
