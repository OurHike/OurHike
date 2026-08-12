import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {
  DetailPicker,
  hikingDetailOptions,
  rasterDetailOptions,
  type DetailOption,
} from './DetailPicker'

// The three reasons a rung can be greyed, and why they must not share a
// sentence. Two predate this file (#298): a level the sheet does not publish,
// and a level nothing can be chosen at right now. The third is #555 - a level
// this PHONE has no room for - and the distinction between it and the first is
// the whole point of the change: "not offered" is a fact about the map, and a
// hiker who reads it when the truth is "your phone is full" goes looking for a
// different map instead of freeing up space.

afterEach(cleanup)

const group = () => within(screen.getByRole('group', { name: /map detail/i }))

/** One rung, priced. Enough to drive the picker without a real sheet. */
function option(id: string, sizeBytes: number | null, recommended = false): DetailOption {
  return { id, label: id[0].toUpperCase() + id.slice(1), sizeBytes, recommended }
}

const LADDER = [
  option('light', 65_000_000),
  option('standard', 315_100_000, true),
  option('fine', 1_184_700_000),
]

const rung = (label: RegExp) => group().getByRole('radio', { name: label })

describe('a level this phone has no room for (#555)', () => {
  it('greys the rung the allowance cannot hold', () => {
    // WebKit's per-origin allowance starts around a gigabyte, and the Fine
    // raster tier is 1.18 GB - so on iOS this rung was offered with a size and
    // a radio button on a phone that could never store it.
    render(
      <DetailPicker
        options={LADDER}
        value="standard"
        onChange={() => {}}
        availableBytes={1_000_000_000}
      />,
    )

    expect(rung(/fine/i)).toBeDisabled()
    expect(rung(/standard/i)).toBeEnabled()
    expect(rung(/light/i)).toBeEnabled()
  })

  it('names the phone rather than the map', () => {
    render(
      <DetailPicker
        options={LADDER}
        value="standard"
        onChange={() => {}}
        availableBytes={1_000_000_000}
      />,
    )

    expect(group().getByText(/no room on this phone/i)).toBeInTheDocument()
    // NOT the sentence a level the sheet does not publish gets. Sharing it
    // would send a hiker looking for a smaller map when what they need is to
    // delete some photos.
    expect(group().queryByText(/not offered/i)).not.toBeInTheDocument()
  })

  it('still shows what the level would cost', () => {
    // Which is exactly what a hiker needs in order to decide what to free up.
    // Replacing the size with the refusal would take that away.
    render(
      <DetailPicker
        options={LADDER}
        value="standard"
        onChange={() => {}}
        availableBytes={1_000_000_000}
      />,
    )

    expect(group().getByText('1.18 GB')).toBeInTheDocument()
  })

  it('does not recommend a rung it is refusing', () => {
    // Two answers to the same question - is this the one to pick - and they
    // cannot both be on screen.
    render(
      <DetailPicker
        options={[option('standard', 315_100_000, true)]}
        value="standard"
        onChange={() => {}}
        availableBytes={100_000_000}
      />,
    )

    expect(group().queryByText(/recommended/i)).not.toBeInTheDocument()
    expect(group().getByText(/no room on this phone/i)).toBeInTheDocument()
  })

  it('cannot be chosen by tapping it', async () => {
    const onChange = vi.fn()
    render(
      <DetailPicker
        options={LADDER}
        value="standard"
        onChange={onChange}
        availableBytes={1_000_000_000}
      />,
    )

    await userEvent.click(rung(/fine/i))

    expect(onChange).not.toHaveBeenCalled()
  })

  it('stays a radio, so it is announced as an unavailable option', () => {
    // #298's reasoning, which this case inherits: a greyed row that is a
    // `<span>` looks the same and reads as nothing at all.
    render(
      <DetailPicker
        options={LADDER}
        value="standard"
        onChange={() => {}}
        availableBytes={1_000_000_000}
      />,
    )

    expect(rung(/fine/i)).toHaveAttribute('type', 'radio')
  })

  it('comes back when the room does', () => {
    // The acceptance criterion. A hiker who frees up space must see the rung
    // return - which is why the allowance is read live rather than latched at
    // mount (lib/useAvailableBytes.ts).
    const { rerender } = render(
      <DetailPicker
        options={LADDER}
        value="standard"
        onChange={() => {}}
        availableBytes={1_000_000_000}
      />,
    )
    expect(rung(/fine/i)).toBeDisabled()

    rerender(
      <DetailPicker
        options={LADDER}
        value="standard"
        onChange={() => {}}
        availableBytes={4_000_000_000}
      />,
    )

    expect(rung(/fine/i)).toBeEnabled()
    expect(group().queryByText(/no room on this phone/i)).not.toBeInTheDocument()
  })

  it('offers everything where the browser will not say', () => {
    // `null` is unknown, not zero. Greying a rung on an unanswered estimate
    // would be a claim about the phone that nothing supports - the same posture
    // dataSaver.ts takes for an absent API, and the same reason Downloads.tsx
    // warns rather than refuses on a tight estimate.
    render(
      <DetailPicker
        options={LADDER}
        value="standard"
        onChange={() => {}}
        availableBytes={null}
      />,
    )

    expect(rung(/fine/i)).toBeEnabled()
    expect(group().queryByText(/no room on this phone/i)).not.toBeInTheDocument()
  })

  it('offers everything when no allowance is passed at all', () => {
    // Every caller that has not been taught about storage keeps its behaviour.
    render(<DetailPicker options={LADDER} value="standard" onChange={() => {}} />)

    expect(rung(/fine/i)).toBeEnabled()
  })

  it('allows a level exactly the size of the allowance', () => {
    // The comparison is "larger than", not "as large as": a map that exactly
    // fits, fits.
    render(
      <DetailPicker
        options={[option('fine', 1_000_000_000)]}
        value="fine"
        onChange={() => {}}
        availableBytes={1_000_000_000}
      />,
    )

    expect(rung(/fine/i)).toBeEnabled()
  })

  it('leaves a chosen level checked even when it no longer fits', () => {
    // The preference is the hiker's. Silently re-pointing it at a smaller map
    // would change what they asked for without telling them - and the greyed
    // rung plus its sentence is the telling.
    render(
      <DetailPicker
        options={LADDER}
        value="fine"
        onChange={() => {}}
        availableBytes={1_000_000_000}
      />,
    )

    expect(rung(/fine/i)).toBeChecked()
    expect(rung(/fine/i)).toBeDisabled()
  })
})

describe('the three greyed cases stay distinguishable', () => {
  it('says "Not offered" for a level the sheet does not publish, whatever the room', () => {
    // A rung that does not exist cannot be a storage problem, so the map's fact
    // wins - and it must, or the hiker frees up space for a Light hiking sheet
    // the pipeline has never cut (lib/hikingDetail.ts).
    render(
      <DetailPicker
        options={hikingDetailOptions()}
        value="standard"
        onChange={() => {}}
        availableBytes={1_000}
      />,
    )

    expect(rung(/light/i)).toBeDisabled()
    expect(group().getByText(/not offered/i)).toBeInTheDocument()
  })

  it('greys everything when locked, without claiming the phone is full', () => {
    render(
      <DetailPicker
        options={rasterDetailOptions()}
        value="standard"
        onChange={() => {}}
        locked
        lockedNote="This map is on the phone."
        availableBytes={4_000_000_000}
      />,
    )

    for (const radio of group().getAllByRole('radio')) expect(radio).toBeDisabled()
    expect(screen.getByText('This map is on the phone.')).toBeInTheDocument()
    expect(group().queryByText(/no room on this phone/i)).not.toBeInTheDocument()
  })

  it('can say both things at once about different rungs', () => {
    // One sheet with no Light cut, on a phone that cannot hold Fine. Both
    // sentences on screen, each against the rung it is about.
    render(
      <DetailPicker
        options={[
          option('light', null),
          option('standard', 300_000_000),
          option('fine', 1_140_000_000),
        ]}
        value="standard"
        onChange={() => {}}
        availableBytes={1_000_000_000}
      />,
    )

    expect(group().getByText(/not offered/i)).toBeInTheDocument()
    expect(group().getByText(/no room on this phone/i)).toBeInTheDocument()
    expect(rung(/standard/i)).toBeEnabled()
  })
})
