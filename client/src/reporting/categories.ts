// What the report window offers, and what each choice actually is (#1133).
//
// This module owns the VOCABULARY of a report — the tiles, their words, and
// which of them may be filed on a single tap. ReportWindow.tsx owns the
// surface; lib/outbox.ts owns what a filed report becomes. The split matters
// because two of the eight entries below are not reports at all, and that is
// the thing a table like this exists to keep straight.
//
// ─────────────────────────────────────────────────────────────────────────
// THREE CORRECTIONS TO THE DESIGN HANDOFF, recorded here because building it
// as written would quietly undo decisions this repository already made.
//
// `closure` IS NOT A REPORT TYPE. The handoff's state sketch puts it in the
// `ReportType` union. screens/ReportTypePicker.tsx has said the opposite since
// #832, in as many words: "deliberately not a `ReportTypeId` ... a stretch
// with two ends and its own table, not an eighth report type". It has its own
// row here, its own callback, its own sheet and its own backend table, and
// `CLOSURE_ROW.id` is deliberately not assignable to `ReportTypeId`.
//
// `unsafe_encounter` IS `bad_hikers`, and `invasive` IS `invasive_species`.
// The handoff names neither correctly. The constants are what the outbox, the
// wire and the moderation queue already speak, so the constants win and the
// handoff's names appear nowhere.
// ─────────────────────────────────────────────────────────────────────────

import type { ReportDraft } from '../lib/outbox'
import type { ReportIconName } from './icons'

/** Every type a report can actually be. `ReportDraft`'s own union, so this
 *  cannot drift from what the outbox and the wire accept. */
export type ReportTypeId = ReportDraft['type']

export interface ReportCategory {
  id: ReportTypeId
  label: string
  /**
   * One line under the label, on every tile.
   *
   * SIX OF THE EIGHT DID NOT HAVE ONE, which read as though those six were
   * self-evident. "Trash" is the one that gives the game away: litter a hiker
   * can pack out, or an overflowing bin that needs a crew with a truck? Those
   * are different reports and the tile was not saying which.
   */
  description: string
  icon: ReportIconName
}

/**
 * The six that file on one tap.
 *
 * Order is the design handoff's, and it is not alphabetical or arbitrary: the
 * four a hiker meets walking come first, then the two that are about what
 * lives there. `animals` and `invasive_species` genuinely overlap — a feral
 * hog is both — which is why they sat adjacent with hints even before this
 * change, and why their descriptions still do the distinguishing.
 */
export const REPORT_CATEGORIES: readonly ReportCategory[] = [
  {
    id: 'blowdown',
    label: 'Blow down',
    description: 'A tree down across the trail',
    icon: 'tree-pine',
  },
  {
    id: 'flooding',
    label: 'Flooding',
    description: 'Water over the trail, or a ford',
    icon: 'waves-horizontal',
  },
  {
    id: 'trash',
    label: 'Trash',
    description: 'Litter, dumped gear, an overflowing bin',
    icon: 'trash-2',
  },
  {
    // THE LABEL BROADENS AND THE CONSTANT DOES NOT (#1133). No migration, no
    // change to anything already filed - only what the tile says.
    //
    // "Shelter repair" was narrower than the thing it collects. The follow-up
    // list for this type covers roof, floor, privy and water at the site,
    // which is site CONDITION rather than carpentry, and a hiker who finds a
    // fouled privy or a dry piped spring should not have to decide whether
    // that counts as "repair" before they can say so.
    //
    // It also squares the tile with #1122, which made `damaged` and `trash`
    // on a CAMPSITE card escalate into this exact type. A campsite escalating
    // into something called "Shelter repair" was the seam showing.
    id: 'shelter_repair',
    label: 'Shelter or campsite',
    description: 'Damage, mess, privy, water at the site',
    icon: 'tent-tree',
  },
  {
    id: 'animals',
    label: 'Animals',
    description: 'Sightings, food raids, anything aggressive',
    icon: 'paw-print',
  },
  {
    id: 'invasive_species',
    label: 'Invasive species',
    description: 'Plants or pests that shouldn’t be here',
    icon: 'sprout',
  },
] as const

/**
 * The two that never file on one tap, and why each is a row rather than a
 * seventh and eighth tile.
 *
 * A tile in that grid promises the thing behind it is the one-tap answer its
 * neighbours are — that is what the grid means now that tapping one FILES.
 * Neither of these can keep that promise, so neither may look like it can.
 * The argument is #832's, generalised: it put the closure below the grid
 * "because a tile in that grid promises the form behind it is the one-tap
 * form its neighbours are, and this one asks for two miles".
 */
export interface HeavyRow {
  label: string
  description: string
  icon: ReportIconName
}

/**
 * A closure. NOT a `ReportTypeId` — see the header. It leaves the report flow
 * entirely for ClosureSheet, which is why this carries no `id` at all: there
 * is no value to smuggle through `onPick`, and giving it one is exactly the
 * mistake the type would then permit.
 */
export const CLOSURE_ROW: HeavyRow = {
  label: 'The trail is closed',
  description:
    'A washout, a slide, a club’s own sign. Asks for the two miles it runs between.',
  icon: 'octagon-x',
}

/**
 * Something unsafe. A real `ReportTypeId` — `bad_hikers` — but never a one-tap
 * file: it is private to club moderators, it never becomes a public pin, and
 * the 911 line has to be readable BEFORE the tap rather than after it.
 * Somebody in trouble right now needs to know this is the wrong tool while
 * they can still act on that, not once they are already in a form.
 */
export const UNSAFE_ROW: HeavyRow & { id: ReportTypeId } = {
  id: 'bad_hikers',
  label: 'Something unsafe happened',
  description:
    'Threats, robbery, being followed. Private to club moderators — never a public pin.',
  icon: 'shield-alert',
}

/**
 * Verbatim from screens/ReportTypePicker.tsx, and it stays verbatim.
 *
 * The handoff asks for that explicitly ("do not reword") and it is right to:
 * this sentence has been read by whoever has used the app so far, it is the
 * one piece of copy on the surface that is about somebody's physical safety,
 * and there is no version of rewording it that is worth the risk of making it
 * worse.
 */
export const EMERGENCY_NOTICE =
  'Call 911 if you are in danger now. This reaches volunteers, sometimes days later.'

/** Whether a tap on this type may write straight to the outbox.
 *
 *  A function rather than a flag on the table, because the answer is a
 *  property of the two rows above rather than of the six tiles — and stating
 *  it positively ("these six file") would mean a type added later defaults to
 *  filing, which is the wrong direction to fail in. */
export function filesOnTap(id: ReportTypeId): boolean {
  return id !== UNSAFE_ROW.id && id !== 'thanks'
}

/** What a filed report is called once it is filed, for the receipt.
 *
 *  Reads off the table rather than holding a second copy of the words, so
 *  "Filed — shelter or campsite at mi 628.4" cannot come to disagree with the
 *  tile that was tapped. */
export function categoryLabel(id: ReportTypeId): string {
  const found = REPORT_CATEGORIES.find((category) => category.id === id)
  if (found !== undefined) return found.label
  if (id === UNSAFE_ROW.id) return UNSAFE_ROW.label
  return id === 'thanks' ? 'Thanks' : id
}
