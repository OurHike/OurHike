// One Lucide icon, drawn at the design's stroke (#1284).
//
// `dangerouslySetInnerHTML` over a string literal this repository wrote -
// nothing here reaches the DOM from a network or a store, which is the same
// argument reporting/ReportWindow.tsx makes for the report icons. The size and
// the colour are the caller's: the icon inherits `currentColor`, so a bus in
// `--accent-blaze-blue` and a search glass in `--brand-primary` are the same
// component under two class names.

import { HIKE_FINDER_ICONS, type HikeFinderIconName } from './hikeFinderIcons'

export interface HikeFinderIconProps {
  name: HikeFinderIconName
  className?: string
  /** 1.5 for the line icons, 2 for the check - the design's own weights. */
  strokeWidth?: number
  /** A label makes the icon announce itself; without one it is decoration
   *  and hidden from assistive tech. */
  label?: string
}

export function HikeFinderIcon({
  name,
  className,
  strokeWidth = 1.5,
  label,
}: HikeFinderIconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      focusable="false"
      className={className}
      {...(label === undefined
        ? { 'aria-hidden': true }
        : { role: 'img', 'aria-label': label })}
      dangerouslySetInnerHTML={{ __html: HIKE_FINDER_ICONS[name] }}
    />
  )
}
