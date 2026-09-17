import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { ReporterDetails, type ReporterDetailsProps } from './ReporterDetails'

afterEach(() => {
  cleanup()
})

// Who a report is signed by, and whether they may be asked more (#1563).
// The wire shape is lib/reporterSignature.ts's; this is the block both
// filing surfaces render, so the words are tested once. The real name is
// the host's draft, handed down - see the header of ReporterDetails.tsx.

function setup(overrides: Partial<ReporterDetailsProps> = {}) {
  const props: ReporterDetailsProps = {
    trailName: 'Switchback',
    signedAs: 'trail',
    onSignedAs: vi.fn(),
    realName: '',
    onRealNameChange: vi.fn(),
    onRealNameSettle: vi.fn(),
    contactOk: false,
    onContactOk: vi.fn(),
    reporterType: 'section',
    ...overrides,
  }
  return { props, ...render(<ReporterDetails {...props} />) }
}

describe('ReporterDetails', () => {
  it('says the whole signature in one sentence, with the kind of hiker other people see', () => {
    setup()
    expect(screen.getByTestId('report-signature')).toHaveTextContent(
      'Signed as Switchback (trail name) · section',
    )
    expect(screen.getByRole('radio', { name: /trail name/i })).toBeChecked()
    // The real name is not set, and the radio says so rather than hiding.
    expect(screen.getByRole('radio', { name: /real name/i })).toHaveAccessibleName(
      /not set/,
    )
    // No field until the real name is chosen.
    expect(screen.queryByTestId('reporter-real-name')).toBeNull()
  })

  it('says "not set" for a trail name nobody has given, rather than inventing one', () => {
    setup({ trailName: null })
    expect(screen.getByTestId('report-signature')).toHaveTextContent(
      'Signed as not set (trail name) · section',
    )
  })

  it('asks the parent for the other name, and shows the field once the real name is chosen', () => {
    const { props, rerender } = setup()
    fireEvent.click(screen.getByRole('radio', { name: /real name/i }))
    expect(props.onSignedAs).toHaveBeenCalledWith('real')

    rerender(<ReporterDetails {...props} signedAs="real" />)
    expect(screen.getByTestId('reporter-real-name')).toHaveValue('')
    expect(screen.getByTestId('report-signature')).toHaveTextContent(
      'Signed as not set (real name) · section',
    )
  })

  it('hands every keystroke to the host and says when the field is left, which is when the host persists', () => {
    const { props } = setup({ signedAs: 'real' })
    const field = screen.getByTestId('reporter-real-name')
    fireEvent.change(field, { target: { value: 'Jane' } })
    expect(props.onRealNameChange).toHaveBeenCalledWith('Jane')
    expect(props.onRealNameSettle).not.toHaveBeenCalled()

    fireEvent.blur(field)
    expect(props.onRealNameSettle).toHaveBeenCalledTimes(1)
  })

  it('shows the draft it is handed, so the summary reads what will be sent', () => {
    setup({ signedAs: 'real', realName: 'Jane Doe' })
    expect(screen.getByTestId('reporter-real-name')).toHaveValue('Jane Doe')
    expect(screen.getByTestId('report-signature')).toHaveTextContent(
      'Signed as Jane Doe (real name) · section',
    )
    cleanup()

    // A name of spaces is none.
    setup({ signedAs: 'real', realName: '   ' })
    expect(screen.getByTestId('report-signature')).toHaveTextContent(
      'Signed as not set (real name) · section',
    )
  })

  it('reports the consent box as a plain yes or no', () => {
    const { props } = setup()
    const box = screen.getByRole('checkbox', { name: /you can contact me/i })
    expect(box).not.toBeChecked()
    fireEvent.click(box)
    expect(props.onContactOk).toHaveBeenCalledWith(true)
  })

  it('says who sees the name and the answer, where the choice is made', () => {
    setup()
    expect(screen.getByTestId('reporter-details')).toHaveTextContent(
      'Only the club moderators who read this report see the name and this answer.',
    )
  })
})
