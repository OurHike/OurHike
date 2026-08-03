// Whether the hiker has told their phone to go easy on data, and what the map
// should do about it.
//
// The live topographic background (features/MAP_OPTIONS.md §1) is the default,
// so without this every hiker with signal pulls vector and DEM tiles whether or
// not they wanted to spend the data on them. Measured over the AT that is
// roughly 2 MB for a fresh view - small next to the 314 MB corridor download,
// and unlike that download it was never asked for. The archive is a size on a
// button someone taps; this was a default someone inherited. That difference is
// the whole reason this module exists, and it is a consent problem rather than
// a cost one: OpenFreeMap is uncapped and the AWS DEM is Open Data with
// sponsored egress, so none of those bytes are billed to the project.
//
// SAVE-DATA WINS, AND IT IS TOLD TO YOUR FACE
//
// Data Saver is a preference the hiker set deliberately, at the OS level, and
// it is a better signal about their plan than our default could ever be - so it
// overrides the background choice rather than merely nudging it.
//
// The cost of that is a settings row that can disagree with what is on screen,
// which is exactly the kind of quiet mismatch value #4 exists to prevent. So
// the rule here is paired with a visible statement in Settings, and neither
// half ships without the other: the app is allowed to override a preference,
// and is not allowed to do it silently.
//
// Worth naming plainly: someone who leaves Data Saver on permanently and
// genuinely wants the topo sheet has to turn Data Saver off to get it, because
// nothing stored distinguishes "chose the live sheet" from "never touched the
// default". Giving those two different answers needs a real "this was chosen"
// flag on the synced preferences - there is precedent in `download_choice_made`
// - and that is a contract change worth deciding rather than assuming.

import type { BackgroundSource } from './userPreferences'

/**
 * The slice of the Network Information API this needs.
 *
 * Hand-written because TypeScript's DOM lib does not declare
 * `navigator.connection` at all, and every field is optional because every
 * field genuinely is: Safari implements none of this, so on iOS the whole
 * object is undefined and everything below answers "not saving data" - which
 * is the honest answer there, not a bug. `@capacitor/network` would close that
 * gap with a real `connectionType`, but Capacitor is not wired up yet.
 */
export interface DataSaverConnection {
  saveData?: boolean
  addEventListener?: (type: 'change', listener: () => void) => void
  removeEventListener?: (type: 'change', listener: () => void) => void
}

type NavigatorWithConnection = Navigator & { connection?: DataSaverConnection }

/** The live connection object, or undefined where the API does not exist. */
export function dataSaverConnection(): DataSaverConnection | undefined {
  if (typeof navigator === 'undefined') return undefined
  return (navigator as NavigatorWithConnection).connection
}

/**
 * True only when the phone actively says data is being saved.
 *
 * Compared against `true` rather than coerced, so a missing API and a browser
 * that reports `undefined` both mean "no" instead of accidentally meaning
 * "yes" - guessing that a hiker is metered and quietly withholding the map
 * would be the worse failure of the two.
 */
export function dataSaverEnabled(): boolean {
  return dataSaverConnection()?.saveData === true
}

/**
 * The background to actually draw, which is not always the one in settings.
 *
 * Deliberately a pure function of the two inputs rather than a lookup inside
 * the map: this is a real decision about someone's money, and it should be
 * readable, testable, and stated in exactly one place that both the map and
 * the settings copy read - so the screen can never claim one thing while the
 * canvas draws another.
 */
export function effectiveBackground(
  preference: BackgroundSource,
  saveData: boolean,
): BackgroundSource {
  return saveData ? 'usgs_topo_offline' : preference
}

/**
 * Whether Data Saver is currently overriding what the hiker picked.
 *
 * Only true when the two actually disagree - Data Saver plus an already-offline
 * choice is not an override, it is agreement, and telling someone their
 * preference was overridden when it was honoured is its own small lie.
 */
export function backgroundOverridden(
  preference: BackgroundSource,
  saveData: boolean,
): boolean {
  return effectiveBackground(preference, saveData) !== preference
}
