// The Today screen (#1054): the redesign's home tab.
//
// This first cut is deliberately the frame and not the furniture - the pine
// header block and the paper column, so the tab lands routable and honest in
// the same commit that creates it. The journal itself (entries ordered by
// distance, the mode switch, the volunteer card) is the next commit's; what
// this one must already get right is the part that cannot be retrofitted:
// offline-first (everything here renders from what the phone holds), and
// nothing on it pretending to know more than the shell told it.

import { formatTodayEyebrow } from '../lib/todayText'
import './today.css'

export interface TodayProps {
  now: Date
  /** The position line, already decided (lib/positionLine.ts) - a sentence,
   *  never a bare number, for HeaderProps' reason: which of the eight
   *  position states is true is the shell's knowledge. */
  position: string
}

export function Today({ now, position }: TodayProps) {
  return (
    <div className="today">
      <header className="today__chrome">
        <p className="today__eyebrow">{formatTodayEyebrow(now)}</p>
        <p className="today__position">{position}</p>
      </header>
      <div className="today__paper">
        {/* Said on the home screen because it is the promise the whole app is
            built around, and the first thing a hiker with one bar of signal
            wonders about a screen full of data. */}
        <p className="today__footer">Everything here works with no signal.</p>
      </div>
    </div>
  )
}
