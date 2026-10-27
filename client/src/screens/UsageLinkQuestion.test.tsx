import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { UsageLinkQuestion } from './UsageLinkQuestion'

// "Link your usage to your account?" (#1902), worded as the maintainer
// approved it (poll 2026-10-27, frame C). The sentence most worth pinning is
// "either way": declining to link does not stop the position being sent, and
// a question that let "No thanks" read otherwise would be a promise nobody
// keeps.

afterEach(cleanup)

describe('UsageLinkQuestion', () => {
  it('asks the question the maintainer approved', () => {
    render(<UsageLinkQuestion onAnswer={vi.fn()} />)

    expect(
      screen.getByRole('heading', { name: 'Link your usage to your account?' }),
    ).toBeInTheDocument()
  })

  it('says the position goes with each count either way, so "No thanks" cannot read as stopping it', () => {
    render(<UsageLinkQuestion onAnswer={vi.fn()} />)

    expect(screen.getByText(/either way/i).closest('li')).toHaveTextContent(
      /your position goes with each count either way while location is on, sealed/i,
    )
  })

  it('says where to stop sharing entirely', () => {
    render(<UsageLinkQuestion onAnswer={vi.fn()} />)

    expect(screen.getByText(/to stop sharing entirely/i)).toHaveTextContent(
      /safety & privacy → share usage statistics/i,
    )
  })

  it('answers yes with "Yes, link it" and no with "No thanks"', async () => {
    const user = userEvent.setup()
    const onAnswer = vi.fn()
    render(<UsageLinkQuestion onAnswer={onAnswer} />)

    await user.click(screen.getByRole('button', { name: 'Yes, link it' }))
    await user.click(screen.getByRole('button', { name: 'No thanks' }))

    expect(onAnswer.mock.calls).toEqual([[true], [false]])
  })
})
