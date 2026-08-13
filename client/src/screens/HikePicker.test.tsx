import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HikePicker } from './HikePicker'

// #335. The screen's whole job is to turn two numbers into a hike without
// letting a hiker save a pair that cannot be one - and to say which way those
// numbers mean as they are typed, rather than offering a NOBO/SOBO control
// that could disagree with them.

const PROPS = {
  hike: null,
  trailMiles: 2197,
  onSave: vi.fn(),
  onClear: vi.fn(),
  onClose: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('saying which way you are walking', () => {
  it('fills both ends from the northbound shortcut', async () => {
    const user = userEvent.setup()
    render(<HikePicker {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /whole trail, northbound/i }))

    expect(screen.getByLabelText(/starting at mile/i)).toHaveValue(0)
    expect(screen.getByLabelText(/finishing at mile/i)).toHaveValue(2197)
  })

  it('fills them the other way round for southbound', async () => {
    const user = userEvent.setup()
    render(<HikePicker {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /whole trail, southbound/i }))

    expect(screen.getByLabelText(/starting at mile/i)).toHaveValue(2197)
    expect(screen.getByLabelText(/finishing at mile/i)).toHaveValue(0)
  })

  it('offers no direction control at all, only the numbers', async () => {
    // There are already two sources of truth for direction if a toggle exists,
    // and they can disagree. `start < end` is the whole rule - the same call
    // backend/app/models/hike.py makes by having no `direction` column.
    render(<HikePicker {...PROPS} />)

    expect(screen.queryByRole('radio', { name: /northbound/i })).toBeNull()
    expect(screen.queryByRole('checkbox', { name: /southbound/i })).toBeNull()
  })

  it('says which way the numbers mean, as they are typed', async () => {
    const user = userEvent.setup()
    render(<HikePicker {...PROPS} />)

    await user.type(screen.getByLabelText(/starting at mile/i), '1450')
    await user.type(screen.getByLabelText(/finishing at mile/i), '1408')

    expect(screen.getByRole('status')).toHaveTextContent('Southbound')
    expect(screen.getByRole('status')).toHaveTextContent('42 mi')
  })

  it('states how far apart they are in the hiker’s units, and the fields in neither', async () => {
    // #619. The one measurement on this screen converts; the two numbers typed
    // into it are mile markers, which are where you are on the A.T. rather
    // than a quantity of anything - so the labels keep saying "mile" under
    // both settings and the readout does not.
    const user = userEvent.setup()
    render(<HikePicker {...PROPS} units="metric" />)

    await user.type(screen.getByLabelText(/starting at mile/i), '1450')
    await user.type(screen.getByLabelText(/finishing at mile/i), '1408')

    expect(screen.getByRole('status')).toHaveTextContent('67.6 km')
    expect(screen.getByLabelText(/finishing at mile/i)).toHaveValue(1408)
  })

  it('hands back the hike the numbers describe', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(<HikePicker {...PROPS} onSave={onSave} />)

    await user.type(screen.getByLabelText(/starting at mile/i), '1408')
    await user.type(screen.getByLabelText(/finishing at mile/i), '2197')
    await user.click(screen.getByRole('button', { name: /^save$/i }))

    expect(onSave).toHaveBeenCalledWith({ startMile: 1408, endMile: 2197 })
  })
})

describe('what it refuses to save', () => {
  it('cannot save an empty form', () => {
    render(<HikePicker {...PROPS} />)

    expect(screen.getByRole('button', { name: /^save$/i })).toBeDisabled()
  })

  it('cannot save the same mile marker twice, and says why', async () => {
    const user = userEvent.setup()
    render(<HikePicker {...PROPS} />)

    await user.type(screen.getByLabelText(/starting at mile/i), '500')
    await user.type(screen.getByLabelText(/finishing at mile/i), '500')

    expect(screen.getByRole('button', { name: /^save$/i })).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent(/two different mile markers/i)
  })

  it('cannot save a mile past the end of the trail', async () => {
    const user = userEvent.setup()
    render(<HikePicker {...PROPS} />)

    await user.type(screen.getByLabelText(/starting at mile/i), '0')
    await user.type(screen.getByLabelText(/finishing at mile/i), '9000')

    expect(screen.getByRole('button', { name: /^save$/i })).toBeDisabled()
  })
})

describe('before the trail data has arrived', () => {
  it('disables the shortcuts, because there is no length to end at', () => {
    render(<HikePicker {...PROPS} trailMiles={null} />)

    expect(
      screen.getByRole('button', { name: /whole trail, northbound/i }),
    ).toBeDisabled()
  })

  it('says why, rather than leaving two dead buttons', () => {
    render(<HikePicker {...PROPS} trailMiles={null} />)

    expect(screen.getByText(/trail data is still arriving/i)).toBeInTheDocument()
  })

  it('still lets someone who knows their mile markers enter them', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(<HikePicker {...PROPS} trailMiles={null} onSave={onSave} />)

    await user.type(screen.getByLabelText(/starting at mile/i), '10')
    await user.type(screen.getByLabelText(/finishing at mile/i), '40')
    await user.click(screen.getByRole('button', { name: /^save$/i }))

    expect(onSave).toHaveBeenCalledWith({ startMile: 10, endMile: 40 })
  })
})

describe('changing your mind', () => {
  it('opens holding the hike that is already set', () => {
    render(<HikePicker {...PROPS} hike={{ startMile: 0, endMile: 2197 }} />)

    expect(screen.getByLabelText(/starting at mile/i)).toHaveValue(0)
    expect(screen.getByLabelText(/finishing at mile/i)).toHaveValue(2197)
  })

  it('offers Clear as an ordinary button once there is something to clear', async () => {
    // Finishing a hike, or changing plans at a road crossing, must not mean
    // clearing app data to get back to the state a hiker started in.
    const user = userEvent.setup()
    const onClear = vi.fn()
    render(
      <HikePicker {...PROPS} hike={{ startMile: 0, endMile: 2197 }} onClear={onClear} />,
    )

    await user.click(screen.getByRole('button', { name: /clear this hike/i }))

    expect(onClear).toHaveBeenCalled()
  })

  it('offers nothing to clear when there is no hike', () => {
    render(<HikePicker {...PROPS} />)

    expect(screen.queryByRole('button', { name: /clear/i })).toBeNull()
  })

  it('leaves without saving on Cancel', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    const onClose = vi.fn()
    render(<HikePicker {...PROPS} onSave={onSave} onClose={onClose} />)

    await user.type(screen.getByLabelText(/starting at mile/i), '10')
    await user.click(screen.getByRole('button', { name: /cancel/i }))

    expect(onClose).toHaveBeenCalled()
    expect(onSave).not.toHaveBeenCalled()
  })
})
