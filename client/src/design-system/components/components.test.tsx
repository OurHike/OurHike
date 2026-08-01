import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { Badge, Button, Callout, Card, Input, Logo, Select } from './index'

afterEach(cleanup)

// The design system shipped without tests. These are not visual-regression
// tests - jsdom does no layout and the styling here is inline CSS variables,
// so a screenshot comparison would assert nothing real. What they do cover is
// the decision-making each component does: tone/variant/size lookups and their
// fallbacks, the conditional slots, and the interactive state Button and Input
// hold.
//
// The fallbacks are the part worth having. Every one of these components reads
// a prop into an object lookup and falls back with `||`, so a typo'd or
// out-of-date tone renders neutral rather than crashing on undefined - and
// that path is only ever exercised by exactly the mistake it exists to absorb.

describe('Badge', () => {
  it('renders its children', () => {
    render(<Badge>Moderate</Badge>)

    expect(screen.getByText('Moderate')).toBeInTheDocument()
  })

  it.each(['easy', 'moderate', 'strenuous', 'info', 'neutral'] as const)(
    'renders the %s tone',
    (tone) => {
      render(<Badge tone={tone}>{tone}</Badge>)

      expect(screen.getByText(tone)).toBeInTheDocument()
    },
  )

  it('falls back to neutral for a tone it does not know', () => {
    // A tone name that has been renamed or mistyped upstream should degrade to
    // the plain treatment, not throw on `undefined.bg`.
    render(<Badge tone={'nonexistent' as 'neutral'}>Unknown</Badge>)

    const badge = screen.getByText('Unknown')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveStyle({ background: 'var(--stone-150)' })
  })
})

describe('Button', () => {
  it('calls onClick when it is pressed', () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Go</Button>)

    fireEvent.click(screen.getByRole('button', { name: 'Go' }))

    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('does not call onClick while disabled', () => {
    const onClick = vi.fn()
    render(
      <Button onClick={onClick} disabled>
        Go
      </Button>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Go' }))

    expect(onClick).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Go' })).toBeDisabled()
  })

  it.each(['primary', 'secondary', 'outline', 'ghost'] as const)(
    'renders the %s variant',
    (variant) => {
      render(<Button variant={variant}>{variant}</Button>)

      expect(screen.getByRole('button', { name: variant })).toBeInTheDocument()
    },
  )

  it.each(['s', 'm', 'l'] as const)('renders at size %s', (size) => {
    render(<Button size={size}>{size}</Button>)

    expect(screen.getByRole('button', { name: size })).toBeInTheDocument()
  })

  it('falls back to the primary variant and medium size for unknown values', () => {
    render(
      <Button variant={'wrong' as 'primary'} size={'xxl' as 'm'}>
        Fallback
      </Button>,
    )

    expect(screen.getByRole('button', { name: 'Fallback' })).toHaveStyle({
      padding: '11px 22px',
    })
  })

  it.each(['primary', 'secondary', 'outline', 'ghost'] as const)(
    'takes a hover background on the %s variant',
    (variant) => {
      render(<Button variant={variant}>{variant}</Button>)
      const button = screen.getByRole('button', { name: variant })
      const resting = button.style.background

      fireEvent.mouseEnter(button)

      expect(button.style.background).not.toBe(resting)
    },
  )

  it('takes a pressed background and shrinks slightly while held', () => {
    render(<Button>Press</Button>)
    const button = screen.getByRole('button', { name: 'Press' })

    fireEvent.mouseEnter(button)
    fireEvent.mouseDown(button)

    expect(button).toHaveStyle({ background: 'var(--brand-primary-press)' })
    expect(button).toHaveStyle({ transform: 'scale(0.97)' })
  })

  it('returns to rest on mouse up', () => {
    render(<Button>Press</Button>)
    const button = screen.getByRole('button', { name: 'Press' })

    fireEvent.mouseEnter(button)
    fireEvent.mouseDown(button)
    fireEvent.mouseUp(button)

    expect(button).toHaveStyle({ transform: 'scale(1)' })
  })

  it('drops both hover and pressed state when the pointer leaves mid-press', () => {
    // Without clearing `active` here a button dragged off would stay visually
    // held down with the pointer somewhere else entirely.
    render(<Button>Press</Button>)
    const button = screen.getByRole('button', { name: 'Press' })

    fireEvent.mouseEnter(button)
    fireEvent.mouseDown(button)
    fireEvent.mouseLeave(button)

    expect(button).toHaveStyle({ transform: 'scale(1)' })
    expect(button).toHaveStyle({ background: 'var(--brand-primary)' })
  })

  it('stays at its resting background while disabled, however it is poked', () => {
    render(<Button disabled>Off</Button>)
    const button = screen.getByRole('button', { name: 'Off' })

    fireEvent.mouseEnter(button)
    fireEvent.mouseDown(button)

    expect(button).toHaveStyle({ background: 'var(--brand-primary)' })
    expect(button).toHaveStyle({ transform: 'scale(1)' })
    expect(button).toHaveStyle({ cursor: 'not-allowed' })
  })

  it('lets a caller override styling', () => {
    render(<Button style={{ marginTop: '4px' }}>Styled</Button>)

    expect(screen.getByRole('button', { name: 'Styled' })).toHaveStyle({ marginTop: '4px' })
  })
})

describe('Card', () => {
  it('renders every slot it is given', () => {
    render(
      <Card
        image={<span>image</span>}
        eyebrow="Eyebrow"
        title="Title"
        meta="Meta"
        footer={<span>footer</span>}
      >
        Body
      </Card>,
    )

    for (const text of ['image', 'Eyebrow', 'Title', 'Meta', 'Body', 'footer']) {
      expect(screen.getByText(text)).toBeInTheDocument()
    }
  })

  it('omits every optional slot that was not given', () => {
    render(<Card>Body only</Card>)

    expect(screen.getByText('Body only')).toBeInTheDocument()
    expect(screen.queryByText('Eyebrow')).not.toBeInTheDocument()
  })
})

describe('Callout', () => {
  it('renders its title, body and action', () => {
    render(
      <Callout title="Heads up" action={<button type="button">Act</button>}>
        Something to know
      </Callout>,
    )

    expect(screen.getByText('Heads up')).toBeInTheDocument()
    expect(screen.getByText('Something to know')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Act' })).toBeInTheDocument()
  })

  it.each(['brand', 'urgent', 'info'] as const)('renders the %s tone', (tone) => {
    render(<Callout tone={tone}>{tone}</Callout>)

    expect(screen.getByText(tone)).toBeInTheDocument()
  })

  it('falls back to the brand tone for one it does not know', () => {
    render(<Callout tone={'nope' as 'brand'} title="Title" />)

    expect(screen.getByText('Title')).toHaveStyle({ color: 'var(--pine-800)' })
  })

  it('renders with neither a title nor a body', () => {
    const { container } = render(<Callout />)

    expect(container.querySelector('div')).toBeInTheDocument()
  })
})

describe('Input', () => {
  // Read off the inline style attribute rather than through toHaveStyle().
  // These borders are shorthands containing a custom property
  // (`1px solid var(--danger)`), and jsdom cannot resolve a var() inside a
  // shorthand - it reports the declaration as empty, so toHaveStyle() compares
  // nothing against nothing and passes for any value at all.
  const borderOf = (el: HTMLElement) =>
    /border:\s*([^;]+)/.exec(el.getAttribute('style') ?? '')?.[1]

  it('renders a labelled field and reports what is typed', () => {
    const onChange = vi.fn()
    render(<Input label="Trail name" value="" onChange={onChange} />)

    fireEvent.change(screen.getByLabelText('Trail name'), { target: { value: 'AT' } })

    expect(onChange).toHaveBeenCalled()
  })

  it('renders without a label', () => {
    render(<Input placeholder="Search" />)

    expect(screen.getByPlaceholderText('Search')).toBeInTheDocument()
  })

  it('shows an error message and marks the border when given one', () => {
    render(<Input label="Email" error="That is not an email address" />)

    expect(screen.getByText('That is not an email address')).toBeInTheDocument()
    // By role, not by label: the error text lives inside the same <label>, so
    // the field's accessible name is "Email That is not an email address".
    expect(borderOf(screen.getByRole('textbox'))).toBe('1px solid var(--danger)')
  })

  it('highlights on focus and drops the highlight on blur', () => {
    render(<Input label="Email" />)
    const input = screen.getByLabelText('Email')

    fireEvent.focus(input)
    expect(borderOf(input)).toBe('1px solid var(--brand-primary)')

    fireEvent.blur(input)
    expect(borderOf(input)).toBe('1px solid var(--border-2)')
  })

  it('keeps the error treatment over the focus treatment', () => {
    // Focus should not paint over the fact that the value is wrong.
    render(<Input label="Email" error="Required" />)
    const input = screen.getByRole('textbox')

    fireEvent.focus(input)

    expect(borderOf(input)).toBe('1px solid var(--danger)')
  })

  it('takes a type other than text', () => {
    render(<Input label="Password" type="password" />)

    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password')
  })
})

describe('Select', () => {
  it('renders its options and reports a change', () => {
    const onChange = vi.fn()
    render(
      <Select label="Units" options={['Miles', 'Kilometres']} value="Miles" onChange={onChange} />,
    )

    fireEvent.change(screen.getByLabelText('Units'), { target: { value: 'Kilometres' } })

    expect(screen.getAllByRole('option')).toHaveLength(2)
    expect(onChange).toHaveBeenCalled()
  })

  it('renders with no label and no options at all', () => {
    const { container } = render(<Select />)

    expect(container.querySelector('select')).toBeInTheDocument()
    expect(screen.queryAllByRole('option')).toHaveLength(0)
  })
})

describe('Logo', () => {
  it('pairs the icon with the wordmark by default', () => {
    render(<Logo />)

    expect(screen.getByText('OurHike')).toBeInTheDocument()
    // The icon is decorative next to a visible wordmark, so it must not also
    // announce itself - that would read the name twice.
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('carries its own accessible name when the wordmark is not there to do it', () => {
    render(<Logo iconOnly />)

    expect(screen.getByRole('img', { name: 'OurHike' })).toBeInTheDocument()
    expect(screen.queryByText('OurHike')).not.toBeInTheDocument()
  })

  it('scales everything from one size, so the lockup keeps its proportions', () => {
    render(<Logo size={48} iconOnly />)

    const icon = screen.getByRole('img', { name: 'OurHike' })
    expect(icon).toHaveAttribute('width', '48')
    expect(icon).toHaveAttribute('height', '48')
    // Half the 96px reference, so the corner radius halves with it.
    expect(icon).toHaveStyle({ borderRadius: '10px' })
  })

  it('lets a caller style the lockup', () => {
    const { container } = render(<Logo style={{ opacity: 0.5 }} />)

    expect(container.firstElementChild).toHaveStyle({ opacity: '0.5' })
  })
})
