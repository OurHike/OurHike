import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ShowPointsToggle } from './ShowPointsToggle'

/**
 * The switch the maintainer asked for on 2026-09-20: "Add a toggle over the
 * map to 'Show Points'."
 *
 * What this file holds is the control's own contract - what it announces and
 * when it can be pressed. The RULE about when it moves on its own is
 * lib/showPoints.test.ts's, and the two are kept apart deliberately: a
 * component test that also owned the rule would have to render a map to state
 * it.
 */
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the Show points switch', () => {
  it('announces as a switch with its state, rather than as a button', () => {
    // A button announces "Show points, button" and never says whether the
    // points are showing, which is the one fact this control exists to carry.
    render(<ShowPointsToggle shown belowSeam={false} onToggle={() => {}} />)

    const control = screen.getByRole('switch', { name: /Show points/ })
    expect(control).toBeEnabled()
    expect(control).toHaveAttribute('aria-checked', 'true')
  })

  it('reads as off when the points are off', () => {
    render(<ShowPointsToggle shown={false} belowSeam={false} onToggle={() => {}} />)

    expect(screen.getByRole('switch', { name: /Show points/ })).toHaveAttribute(
      'aria-checked',
      'false',
    )
  })

  it('calls back once per tap', async () => {
    const onToggle = vi.fn()
    render(<ShowPointsToggle shown={false} belowSeam={false} onToggle={onToggle} />)

    await userEvent.click(screen.getByRole('switch', { name: /Show points/ }))

    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('stays on screen below the seam, disabled and saying why', async () => {
    // THE MAINTAINER'S PICK from three drawn frames, and the reason is the
    // failure it prevents: a control that disappears below the seam leaves a
    // hiker on the corridor view with an empty map and nothing to explain it.
    const onToggle = vi.fn()
    render(<ShowPointsToggle shown={false} belowSeam onToggle={onToggle} />)

    const control = screen.getByRole('switch', { name: /Show points/ })
    expect(control).toBeDisabled()
    expect(screen.getByText('Zoom in to show waypoints')).toBeInTheDocument()

    await userEvent.click(control)
    expect(onToggle).not.toHaveBeenCalled()
  })

  it('never reads as on below the seam, whatever the switch remembers', () => {
    // A hiker who switched points ON and then zoomed out to the corridor view
    // has a switch that remembers "on" and a map drawing nothing. Announcing
    // "on" there would be the control lying about the screen; the layers' own
    // floors are what is actually deciding.
    render(<ShowPointsToggle shown belowSeam onToggle={() => {}} />)

    expect(screen.getByRole('switch', { name: /Show points/ })).toHaveAttribute(
      'aria-checked',
      'false',
    )
  })

  it('points a screen reader at the reason, and only when there is one', () => {
    const { rerender } = render(
      <ShowPointsToggle shown={false} belowSeam onToggle={() => {}} />,
    )
    const described = screen.getByRole('switch', { name: /Show points/ })
    expect(described).toHaveAttribute('aria-describedby', 'show-points-why')

    rerender(<ShowPointsToggle shown={false} belowSeam={false} onToggle={() => {}} />)
    expect(screen.getByRole('switch', { name: /Show points/ })).not.toHaveAttribute(
      'aria-describedby',
    )
  })
})
