import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'

describe('App scaffold', () => {
  it('renders the design-system Button and Card', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: /design system ok/i })).toBeInTheDocument()
    expect(screen.getByText('OurHike')).toBeInTheDocument()
  })
})
