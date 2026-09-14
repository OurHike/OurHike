import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import {
  SheetGrip,
  useSheetDrag,
  SHEET_FULL_FRACTION,
  SHEET_REST_FRACTION,
} from './SheetGrip'

afterEach(cleanup)

/**
 * A stand-in for the two sheets that carry a grip, with the same three parts:
 * the grip, a scrolling body, and a foot that must never be the thing that
 * scrolls away.
 *
 * WHAT THIS FILE CAN AND CANNOT PROVE. jsdom has no layout - every
 * `offsetHeight` is 0 - so the heights the grip computes cannot be checked
 * here, and pretending otherwise would be the failure mode this whole feature
 * was born from (a test that measured something other than what a hiker gets).
 * The pixels are asserted in e2e/data/builder.spec.ts against a real browser
 * at two phone sizes. What IS provable here is the part a hiker reaches with
 * something other than a thumb: that the grip is a real button, that it says
 * where the sheet is, and that a keyboard can put the sheet anywhere a drag
 * can.
 */
function Sheet({ enabled = true }: { enabled?: boolean }) {
  const drag = useSheetDrag(enabled)
  return (
    <div className="day-hike-bar" ref={drag.attachSheet}>
      {enabled && <SheetGrip drag={drag} label="The builder" />}
      <div className="day-hike-bar__body" data-sheet-body>
        <p>Tap a trail to walk it.</p>
      </div>
      <div className="day-hike-bar__foot" data-sheet-foot>
        <button type="button">Use this route</button>
      </div>
    </div>
  )
}

const grip = () => screen.getByRole('button', { name: /builder is/i })
const sheet = () => document.querySelector('.day-hike-bar')

describe('the planning sheet grip', () => {
  it('opens at rest, and says so in its own name', () => {
    render(<Sheet />)

    expect(sheet()?.getAttribute('data-snap')).toBe('rest')
    expect(grip()).toHaveAccessibleName(/half up/i)
  })

  it('cycles rest, all the way up, out of the way when pressed', async () => {
    const user = userEvent.setup()
    render(<Sheet />)

    await user.click(grip())
    expect(sheet()?.getAttribute('data-snap')).toBe('full')
    expect(grip()).toHaveAccessibleName(/all the way up/i)

    await user.click(grip())
    expect(sheet()?.getAttribute('data-snap')).toBe('peek')
    expect(grip()).toHaveAccessibleName(/out of the way/i)

    // Back round, so a hiker who overshoots gets there by pressing again
    // rather than by learning a second gesture.
    await user.click(grip())
    expect(sheet()?.getAttribute('data-snap')).toBe('rest')
  })

  it('takes the sheet anywhere the drag does, from the keyboard', async () => {
    const user = userEvent.setup()
    render(<Sheet />)

    grip().focus()
    await user.keyboard('{ArrowUp}')
    expect(sheet()?.getAttribute('data-snap')).toBe('full')

    await user.keyboard('{ArrowDown}')
    expect(sheet()?.getAttribute('data-snap')).toBe('rest')
    await user.keyboard('{ArrowDown}')
    expect(sheet()?.getAttribute('data-snap')).toBe('peek')

    // And stops rather than wrapping, because an arrow key is a nudge and a
    // nudge that jumps to the far end is a nudge nobody meant.
    await user.keyboard('{ArrowDown}')
    expect(sheet()?.getAttribute('data-snap')).toBe('peek')

    await user.keyboard('{End}')
    expect(sheet()?.getAttribute('data-snap')).toBe('full')
    await user.keyboard('{Home}')
    expect(sheet()?.getAttribute('data-snap')).toBe('peek')
  })

  it('never writes a height it has not measured', async () => {
    const user = userEvent.setup()
    render(<Sheet />)

    // jsdom reports every box as 0, which is exactly the state a real browser
    // is in for one frame before first layout. A sheet set to `height: 0px`
    // there has swallowed the way on, so the guard is that nothing is written
    // at all until there is something real to write.
    await user.click(grip())
    expect(sheet()?.getAttribute('style') ?? '').not.toContain('height')
  })

  it('leaves the sheet alone where there is nothing to get out of the way of', () => {
    // The desktop rail and the docked card: the sheet is not over a map, so
    // there is no grip and no inline height.
    render(<Sheet enabled={false} />)

    expect(screen.queryByRole('button', { name: /builder is/i })).toBeNull()
    expect(sheet()?.hasAttribute('data-snap')).toBe(false)
    expect(sheet()?.getAttribute('style') ?? '').not.toContain('height')
  })

  it('keeps a strip of map above a sheet pulled all the way up', () => {
    // The one relationship between the two fractions that has to hold: a
    // sheet can never take the whole canvas, or its grip - the only thing
    // that can push it back down - goes with it.
    expect(SHEET_FULL_FRACTION).toBeLessThan(1)
    expect(SHEET_REST_FRACTION).toBeLessThan(SHEET_FULL_FRACTION)
  })
})
