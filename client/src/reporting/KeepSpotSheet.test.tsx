import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { KeepSpotSheet, type KeepSpotSheetProps } from './KeepSpotSheet'

afterEach(() => {
  cleanup()
})

// Keeping a spot marked on the map, as a window (#1563). Three ways out and
// what each means is the whole of it: Keep commits, "Tap again" and every
// dismissal clear the aim, and Cancel in the header leaves the map.

function setup(overrides: Partial<KeepSpotSheetProps> = {}) {
  const props: KeepSpotSheetProps = {
    words: 'mi 628.4',
    onKeep: vi.fn(),
    onTapAgain: vi.fn(),
    onCancel: vi.fn(),
    ...overrides,
  }
  return { props, ...render(<KeepSpotSheet {...props} />) }
}

describe('KeepSpotSheet', () => {
  it('is a dialog named "Keep this spot?" that announces the answer the tap got', () => {
    setup()
    const sheet = screen.getByRole('dialog', { name: 'Keep this spot?' })
    expect(sheet).toHaveFocus()
    expect(screen.getByRole('status')).toHaveTextContent('mi 628.4')
    // Said in the same words the plate and the bar use, whichever answer.
    cleanup()
    setup({ words: 'This spot' })
    expect(screen.getByTestId('keep-spot-words')).toHaveTextContent('This spot')
  })

  it('keeps on Keep and nothing else', () => {
    const { props } = setup()
    fireEvent.click(screen.getByTestId('keep-spot-keep'))
    expect(props.onKeep).toHaveBeenCalledTimes(1)
    expect(props.onTapAgain).not.toHaveBeenCalled()
    expect(props.onCancel).not.toHaveBeenCalled()
  })

  it('clears the aim on "Tap again", on Escape and on a tap beside the window', () => {
    const { props } = setup()
    fireEvent.click(screen.getByTestId('keep-spot-again'))
    fireEvent.keyDown(document, { key: 'Escape' })
    fireEvent.click(screen.getByTestId('keep-spot-scrim'))
    expect(props.onTapAgain).toHaveBeenCalledTimes(3)
    expect(props.onCancel).not.toHaveBeenCalled()
    expect(props.onKeep).not.toHaveBeenCalled()
  })

  it('leaves the map on Cancel, which is the header button', () => {
    const { props } = setup()
    fireEvent.click(screen.getByTestId('keep-spot-cancel'))
    expect(props.onCancel).toHaveBeenCalledTimes(1)
    expect(props.onTapAgain).not.toHaveBeenCalled()
  })

  it('says the spot was marked by hand, which is what the report will carry', () => {
    setup()
    expect(screen.getByRole('dialog')).toHaveTextContent('Marked by hand on the map')
  })
})
