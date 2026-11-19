import { render, screen, within } from '@testing-library/react'
import { expect, it } from 'vitest'
import { fixtureSummary } from '../fixtures'
import { AnalysisScreen } from './AnalysisScreen'

it('AnalysisScreen counts the sites by priority and crew size from summary.priority_by_crew', () => {
  render(<AnalysisScreen summary={fixtureSummary} />)
  const table = screen.getByRole('table')
  const p1 = within(table).getByRole('rowheader', { name: /P1/ }).closest('tr')!
  const counts = fixtureSummary.priority_by_crew.find((r) => r.tier === 'P1')!
  expect(
    within(p1)
      .getAllByRole('cell')
      .map((c) => c.textContent),
  ).toEqual([counts.one_person, counts.team, counts.crew, counts.total].map(String))
})

it('AnalysisScreen says the camping rules are unreviewed and names the sites with no directions', () => {
  render(<AnalysisScreen summary={fixtureSummary} />)
  const unknowns = screen
    .getByRole('heading', { name: "What this doesn't know yet" })
    .closest('section')!
  expect(unknowns).toHaveTextContent('0 land units reviewed so far')
  expect(unknowns).toHaveTextContent('1 site has no walking directions')
})
