import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type RefObject,
} from 'react'

/**
 * A planning sheet the hiker can pull up and push down, and the grip that
 * does it.
 *
 * WHY THIS EXISTS. The day-hike builder puts a sheet over the bottom of the
 * map and the map is where the walk is chosen, so the sheet and the thing it
 * covers are in direct competition for the screen. Every fixed answer to that
 * is wrong for somebody: a tall sheet hides the trail you are trying to tap, a
 * short one hides the route you are trying to read. #1374's 75% floor
 * (2026-09-12) was the short answer taken to its limit and it measured badly -
 * at 375x667 the step rail ended up UNDERNEATH the pinned foot, because the
 * budget left 90 px for 96 px of furniture.
 *
 * The maintainer's read after seeing that measurement, 2026-09-14: "I don't
 * need a hard 75%. I need the ability to pull up or push down the planning
 * options." So the height stops being a constant this file argues about and
 * becomes a thing the hand does.
 *
 * THE MAP STAYS LIVE THE WHOLE TIME. The sheet is an overlay anchored to the
 * canvas floor (screens/plan.css) with no scrim over the map behind it, so a
 * tap above the sheet's top edge has always reached the map - that part was
 * never broken. What was missing is the ability to move the edge.
 */

/** Where a sheet comes to rest when the hand lets go. */
export type SheetSnap = 'peek' | 'rest' | 'full'

export const SHEET_SNAPS: readonly SheetSnap[] = ['peek', 'rest', 'full']

/**
 * The share of the canvas a sheet takes at `rest`.
 *
 * @unvalidated Picked, not measured. It leaves the map about two thirds of the
 * canvas, which is 3.5x the 19% the builder measured before #1374 touched it
 * (2026-09-12) and comfortably more than the 38 px the 75% floor left the
 * review to render in. What would settle it is where hikers actually leave the
 * sheet once they can move it at all - a distribution nothing in this app
 * records today, and the first thing worth recording if the grip earns its
 * keep.
 */
export const SHEET_REST_FRACTION = 0.34

/**
 * The most of the canvas a sheet may take, pulled all the way up.
 *
 * Not 1: the sheet's top edge is the only place left to grab it, so a sheet
 * that reached the canvas ceiling could never be pushed back down. The 15%
 * left over keeps a strip of map above the grip at every snap - both a handle
 * and the reminder that the map is still under there.
 *
 * 0.85 rather than any other number because `.day-hike-card` in
 * screens/plan.css has capped itself at `max-height: 85%` since long before
 * this grip existed, and that cap still governs the SAVED card over the map,
 * which has no grip to rescue it. Were the two to disagree, this file would
 * hand back a height the cascade then refused and the sheet would stop where
 * the hiker had not put it. Change one and change the other.
 */
export const SHEET_FULL_FRACTION = 0.85

/**
 * A drag has to beat this many pixels before it counts as a drag rather than a
 * press, so a thumb that rolls slightly on a tap still cycles the snap.
 *
 * @unvalidated 6 px is the conventional slop for this and nobody here has
 * measured it against a real thumb. What would settle it is the smallest value
 * at which taps stop being read as one-pixel drags on a real device.
 */
const DRAG_SLOP_PX = 6

interface SheetHeights {
  peek: number
  rest: number
  full: number
}

const EMPTY_HEIGHTS: SheetHeights = { peek: 0, rest: 0, full: 0 }

/**
 * Measure the three heights off the sheet as it currently stands.
 *
 * `peek` is DERIVED, not picked: it is the sheet with its scrolling body
 * closed to nothing - the grip, the step rail if there is one, the foot, and
 * the padding and gaps between them. Adding a row to a sheet therefore cannot
 * break peek, and neither can a longer translation, a larger text setting or a
 * foot that wraps onto two lines. That is the invariant the 75% floor broke by
 * assuming 96 px of furniture would fit in a 90 px budget (2026-09-12); a
 * measurement cannot make that mistake, an arithmetic can.
 *
 * `full` is the content's own height, so a sheet is never taller than it has
 * anything to say - the grip pulls up to the route's last line and stops.
 */
function measure(sheet: HTMLElement): SheetHeights {
  const view = sheet.ownerDocument.defaultView
  if (view === null) return EMPTY_HEIGHTS
  // An overlay sheet is sized against the canvas it floats over; a panel in
  // the flow is sized against the column it shares with the map, because that
  // column is exactly what the two of them are dividing.
  const room =
    view.getComputedStyle(sheet).position === 'absolute'
      ? (sheet.offsetParent as HTMLElement | null)
      : sheet.parentElement
  const canvasHeight = room?.clientHeight ?? view.innerHeight ?? 0
  if (canvasHeight === 0) return EMPTY_HEIGHTS

  const body = sheet.querySelector<HTMLElement>('[data-sheet-body]')
  const style = view.getComputedStyle(sheet)
  const pad =
    (Number.parseFloat(style.paddingTop) || 0) +
    (Number.parseFloat(style.paddingBottom) || 0)
  const gap = Number.parseFloat(style.rowGap) || 0

  // Everything that is NOT the scrolling body, plus the gaps between them.
  // Absolutely positioned children - the card's × - take no room in the
  // column and must not be counted, or peek grows by a button nobody sees.
  let furniture = pad
  let inColumn = 0
  for (const child of Array.from(sheet.children)) {
    if (!(child instanceof HTMLElement)) continue
    if (view.getComputedStyle(child).position === 'absolute') continue
    inColumn += 1
    if (child === body) continue
    furniture += child.offsetHeight
  }
  furniture += gap * Math.max(inColumn - 1, 0)

  // scrollHeight is the content's own height even while the box is capped
  // shorter, which is the whole point: it says how tall the sheet WOULD be.
  // With a body that scrolls, the sheet's own scrollHeight no longer carries
  // the overflow, so the body's does.
  const content = furniture + (body === null ? sheet.scrollHeight : body.scrollHeight)
  const ceiling = Math.round(canvasHeight * SHEET_FULL_FRACTION)

  const peek = Math.min(furniture, ceiling)
  const full = Math.min(Math.max(content, peek), ceiling)
  const rest = Math.min(
    Math.max(peek, Math.round(canvasHeight * SHEET_REST_FRACTION)),
    full,
  )

  return { peek, rest, full }
}

function nearestSnap(height: number, heights: SheetHeights): SheetSnap {
  let best: SheetSnap = 'rest'
  let bestGap = Number.POSITIVE_INFINITY
  for (const snap of SHEET_SNAPS) {
    const gap = Math.abs(heights[snap] - height)
    if (gap < bestGap) {
      bestGap = gap
      best = snap
    }
  }
  return best
}

/**
 * Own a sheet's height, and hand back the two things that drive it: a ref for
 * the sheet and the handlers for its grip.
 *
 * The height is written straight onto the element during a drag rather than
 * held in React state. A drag produces a pointermove per frame and a re-render
 * per frame would make the sheet lag the thumb it is supposed to be following;
 * state carries the SNAP, which changes once per gesture.
 */
export interface SheetDragOptions {
  /**
   * Which edge the grip sits on, which is also which way a drag grows the
   * surface. `top` is a sheet anchored to the canvas floor - the builder, the
   * review - where pulling UP makes it taller. `bottom` is a panel in the flow
   * above the map - step 2's "Your route" - where the grip is its lower edge
   * and pulling DOWN makes it taller. Getting this backwards is not a subtle
   * bug: the surface runs away from the thumb.
   */
  edge?: 'top' | 'bottom'
}

function useSheetDrag(
  elementRef: RefObject<HTMLElement | null>,
  options: SheetDragOptions = {},
) {
  const edge = options.edge ?? 'top'
  const [snap, setSnap] = useState<SheetSnap>('rest')
  const heightsRef = useRef<SheetHeights>(EMPTY_HEIGHTS)
  const snapRef = useRef<SheetSnap>(snap)
  const dragRef = useRef<{
    startY: number
    startHeight: number
    moved: boolean
    /** The height last written, which is what the release snaps from. */
    applied: number
  } | null>(null)
  // Bumped by a viewport resize so the layout effect below re-measures.
  const [resizeTick, setResizeTick] = useState(0)

  const apply = useCallback((height: number) => {
    const element = elementRef.current
    if (element === null) return
    element.style.height = `${Math.round(height)}px`
  }, [])

  // Re-measure after every render: the sheet's content changes as stops land
  // on the route, and `rest` is capped by that content so it has to follow.
  // Writing style.height does not schedule a React render, so this settles
  // rather than looping.
  useLayoutEffect(() => {
    const element = elementRef.current
    if (element === null) return
    // `data-snap` FIRST, because it is what turns `__body` from
    // `display: contents` into a real scroller (screens/plan.css). Measuring
    // before it is set reads a body with no box at all, and every sheet comes
    // out exactly as tall as its own furniture.
    element.setAttribute('data-snap', snap)
    // Then measure against the sheet's natural box, or `full` reads back
    // whatever we last set rather than what the content wants.
    const previous = element.style.height
    element.style.removeProperty('height')
    const heights = measure(element)
    element.style.height = previous
    heightsRef.current = heights
    if (heights.full === 0) return
    if (dragRef.current === null) apply(heights[snap])
  })

  // The pointer and key handlers read the snap through a ref rather than the
  // closure, because they are registered on the DOM for the life of a gesture
  // and a stale closure would snap the sheet back to where it was two
  // gestures ago. Synced in an effect, never during render.
  useEffect(() => {
    snapRef.current = snap
  }, [snap])

  // ONE EXTRA RENDER ON MOUNT, and it is load-bearing. This grip is a CHILD of
  // the sheet it measures, and React attaches a ref during the same bottom-up
  // walk that runs layout effects - so on the first commit the child's layout
  // effect runs BEFORE the parent div's ref is attached, and finds `null`
  // where the sheet should be. A passive effect runs after that whole walk, by
  // which time the ref is there; bumping the tick sends the layout effect
  // round once more with something to measure. Without it the sheet mounts
  // with no `data-snap` and no height at all, which is how the first version
  // of this shipped and how the unit test caught it.
  useEffect(() => {
    setResizeTick((tick) => tick + 1)
  }, [])

  useEffect(() => {
    const onResize = () => setResizeTick((tick) => tick + 1)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // Hand the sheet back as it was found. A hiker who rotates a phone across
  // the desktop breakpoint unmounts this grip, and a sheet left carrying an
  // inline height and a `data-snap` would keep a phone's geometry inside a
  // laptop's rail.
  useEffect(() => {
    const element = elementRef.current
    return () => {
      element?.style.removeProperty('height')
      element?.removeAttribute('data-snap')
    }
  }, [elementRef])
  void resizeTick

  const settle = useCallback(
    (next: SheetSnap) => {
      setSnap(next)
      const element = elementRef.current
      if (element === null) return
      element.setAttribute('data-snap', next)
      // Never write a height off an unmeasured sheet. Under jsdom, and for one
      // frame before the first layout, every height is 0 - and a sheet set to
      // 0 px is a sheet that has swallowed the way on.
      if (heightsRef.current.full > 0) apply(heightsRef.current[next])
    },
    [apply],
  )

  const onPointerDown = useCallback(
    (event: React.PointerEvent<HTMLElement>) => {
      const element = elementRef.current
      if (element === null) return
      // Only the primary button, and never a gesture the browser is already
      // treating as a scroll.
      if (event.button !== 0) return
      event.currentTarget.setPointerCapture?.(event.pointerId)
      const startHeight = element.getBoundingClientRect().height
      dragRef.current = {
        startY: event.clientY,
        startHeight,
        moved: false,
        applied: startHeight,
      }
      // The snap animates; the drag must not. With the transition left on, the
      // sheet eases toward each frame's height and never arrives, so the
      // release reads a rectangle 100 px behind the thumb and snaps back to
      // where the gesture started. Measured 2026-09-14: a 120 px drag up from
      // rest at 390x844 settled on rest.
      element.setAttribute('data-dragging', '')

      const target = event.currentTarget
      const heights = heightsRef.current

      const onMove = (move: PointerEvent) => {
        const drag = dragRef.current
        if (drag === null) return
        // The grip's own edge decides the sign. On a sheet gripped at the top,
        // travelling toward the top of the screen makes it taller; on a panel
        // gripped at the bottom, travelling toward the bottom does.
        const delta =
          edge === 'top' ? drag.startY - move.clientY : move.clientY - drag.startY
        if (!drag.moved && Math.abs(delta) < DRAG_SLOP_PX) return
        drag.moved = true
        drag.applied = Math.min(
          Math.max(drag.startHeight + delta, heights.peek),
          heights.full,
        )
        apply(drag.applied)
      }

      const onUp = () => {
        const drag = dragRef.current
        dragRef.current = null
        elementRef.current?.removeAttribute('data-dragging')
        target.removeEventListener('pointermove', onMove)
        target.removeEventListener('pointerup', onUp)
        target.removeEventListener('pointercancel', onUp)
        if (drag === null) return
        if (!drag.moved) {
          // A press rather than a drag: cycle, so the grip works for a thumb
          // that taps and for a pointer that cannot drag at all.
          const order = SHEET_SNAPS
          const next = order[(order.indexOf(snapRef.current) + 1) % order.length]
          settle(next)
          return
        }
        // From the height last WRITTEN, not the one currently rendered: even
        // with the transition off, a rect read in the same frame as the last
        // write can still be the previous layout.
        settle(nearestSnap(drag.applied, heightsRef.current))
      }

      target.addEventListener('pointermove', onMove)
      target.addEventListener('pointerup', onUp)
      target.addEventListener('pointercancel', onUp)
    },
    [apply, edge, elementRef, settle],
  )

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLElement>) => {
      const index = SHEET_SNAPS.indexOf(snapRef.current)
      let next: SheetSnap | null = null
      if (event.key === 'ArrowUp')
        next = SHEET_SNAPS[Math.min(index + 1, SHEET_SNAPS.length - 1)]
      else if (event.key === 'ArrowDown') next = SHEET_SNAPS[Math.max(index - 1, 0)]
      else if (event.key === 'Home') next = 'peek'
      else if (event.key === 'End') next = 'full'
      if (next === null) return
      event.preventDefault()
      settle(next)
    },
    [settle],
  )

  return { snap, onPointerDown, onKeyDown }
}

const SNAP_LABEL: Record<SheetSnap, string> = {
  peek: 'out of the way',
  rest: 'half up',
  full: 'all the way up',
}

/**
 * The grip itself: the sheet's top edge, and the only thing on this screen
 * whose job is to get out of the map's way.
 *
 * It is a button, not a bare div with a pointer handler, so that a hiker who
 * cannot drag - a keyboard, a switch, a shaky hand on a cold morning - still
 * reaches every height the drag reaches. Arrow keys step a snap, Home and End
 * take the ends, and a plain press cycles.
 */
export default function SheetGrip({
  sheet,
  label,
  edge,
}: {
  /** The sheet this grip sizes. A ref rather than a DOM id, so nothing here
   *  has to agree with anything about the document. */
  sheet: RefObject<HTMLElement | null>
  /** What the sheet is, for the button's name: "The builder", "The review". */
  label: string
  edge?: 'top' | 'bottom'
}) {
  const drag = useSheetDrag(sheet, { edge })
  return (
    <button
      type="button"
      className="sheet-grip"
      data-sheet-grip
      aria-label={`${label} is ${SNAP_LABEL[drag.snap]}. Drag to resize it, or press to change its height.`}
      onPointerDown={drag.onPointerDown}
      onKeyDown={drag.onKeyDown}
    >
      <span className="sheet-grip__bar" aria-hidden="true" />
    </button>
  )
}
