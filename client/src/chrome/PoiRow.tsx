// One waypoint in a list (#1373, the flow review's PoiRow component).
//
// Today's "Ahead of you", step 3's "Water on route", the follow card's
// "What's left today" and the Map tab's "In view" pull-up all list waypoints,
// and the review's rule is that "every list row is the same component as the
// card it opens". This is that row: the map's own pin at row scale
// (map/MapIcon.tsx, so the shape a hiker learns on the map is the shape in the
// list), a title, a meta line in mono because it carries figures, and an
// optional trailing figure - "0.4 mi" - for the lists that are ordered by it.
//
// The glyph is the waypoint's TYPE and nothing more. Kinds that are not
// waypoints get the two marks the review gives them: a serious warning is the
// warning pin (map/warningPin.ts), and a finish is a flag. Anything this build
// has never heard of gets the neutral diamond, the same as on the map.
//
// A row is a button only when it opens something. A row with no `onOpen` is
// a `div`, so a list of facts is not a list of controls that do nothing.

import { WARNING_ICON_ID } from '../map/warningPin'
import { MapIcon, type MapIconProps } from '../map/MapIcon'
import './poiRow.css'

export type PoiRowKind = string | 'warning' | 'finish' | 'dot'

export interface PoiRowProps {
  /** A POI type (`water`, `shelter`…), `warning` for a serious warning,
   *  `finish` for the end of a walk, or `dot` for a plain marker. */
  kind: PoiRowKind
  title: string
  /** Figures and facts, in mono: "0.8 mi · water · flowing 3 days ago". */
  meta?: string
  /** A right-hand figure, for lists ordered by it. */
  trailing?: string
  /** The pin's rim: broken where nobody has verified the place exists. */
  confidence?: MapIconProps['confidence']
  onOpen?: () => void
  className?: string
}

function Flag() {
  return (
    <svg
      className="poi-row__flag"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M5 3v18M5 4h11l-2 4 2 4H5"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}

function Glyph({
  kind,
  confidence,
}: {
  kind: PoiRowKind
  confidence?: MapIconProps['confidence']
}) {
  if (kind === 'dot') return <span className="poi-row__dot" aria-hidden="true" />
  if (kind === 'finish') return <Flag />
  return (
    <MapIcon
      className="poi-row__pin"
      type={kind === 'warning' ? WARNING_ICON_ID : kind}
      confidence={confidence}
    />
  )
}

export function PoiRow({
  kind,
  title,
  meta,
  trailing,
  confidence,
  onOpen,
  className,
}: PoiRowProps) {
  const classes = ['poi-row', className].filter(Boolean).join(' ')
  const body = (
    <>
      <Glyph kind={kind} confidence={confidence} />
      <span className="poi-row__text">
        <span className="poi-row__title">{title}</span>
        {meta !== undefined && <span className="poi-row__meta">{meta}</span>}
      </span>
      {trailing !== undefined && <span className="poi-row__trailing">{trailing}</span>}
    </>
  )

  if (onOpen === undefined) return <div className={classes}>{body}</div>
  return (
    <button type="button" className={`${classes} poi-row--opens`} onClick={onOpen}>
      {body}
    </button>
  )
}
