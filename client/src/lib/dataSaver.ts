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
// It wins over the CHOICE, though, not over having a map at all. See
// effectiveBackground: with nothing downloaded, "the downloaded corridor only"
// draws no corridor, and subtracting the live sheet on top of that leaves a
// hiker holding blank paper. Both overrides wait until there is a download to
// fall back on.
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
 * Deliberately a pure function of its inputs rather than a lookup inside the
 * map: this is a real decision about someone's money, and it should be
 * readable, testable, and stated in exactly one place that both the map and
 * the settings copy read - so the screen can never claim one thing while the
 * canvas draws another.
 *
 * NOTHING DOWNLOADED OUTRANKS BOTH OTHER INPUTS
 *
 * `usgs_topo_offline` means "draw the downloaded corridor and fetch nothing".
 * With no corridor on the phone, the second half is all that is left: the
 * archive source resolves to nothing, the live layers were never added, and
 * what the hiker gets is the flat paper backdrop and their trail line on it.
 * That is not a cheaper map, it is no map, and no one chose it - not the
 * hiker who picked "downloaded only" expecting their download to show, and
 * not the one whose phone is in Data Saver.
 *
 * So the offline background is only honoured once there is something offline
 * to honour it with. Until then the live sheet is drawn, which is the only
 * setting either of them can actually see. Once the download lands, both
 * choices take effect exactly as before, and this rule never fires again.
 *
 * The cost is real and belongs in the open: a hiker in Data Saver with no
 * download now pulls roughly 2 MB for a fresh view they did not ask for.
 * Weighed against the alternative - an app that opens on blank paper and
 * offers no way to understand why - that is the better failure, and it is
 * the one the maintainer asked for. It does not weaken the consent rule
 * anywhere it still protects something: with a download on the phone, Data
 * Saver still subtracts the live sheet and nothing can turn it back on.
 */
export function effectiveBackground(
  preference: BackgroundSource,
  saveData: boolean,
  archiveDownloaded: boolean,
): BackgroundSource {
  if (!archiveDownloaded) return 'hiking_topo_live'
  return saveData ? 'usgs_topo_offline' : preference
}

/**
 * Why the background being drawn is not the one the hiker picked, if it isn't.
 *
 * A reason rather than a boolean, because the two cases need opposite copy:
 * Data Saver is the app withholding something, and an undownloaded archive is
 * the app supplying something. A screen that told a hiker "Data Saver is on"
 * while the map was busy fetching tiles would be exactly the quiet mismatch
 * this module exists to prevent, one word further along.
 *
 * `null` whenever the drawn background and the preference agree - saying
 * "overridden" to someone whose choice was honoured is its own small lie.
 */
export type BackgroundOverride = 'data-saver' | 'nothing-downloaded'

export function backgroundOverride(
  preference: BackgroundSource,
  saveData: boolean,
  archiveDownloaded: boolean,
): BackgroundOverride | null {
  if (effectiveBackground(preference, saveData, archiveDownloaded) === preference) {
    return null
  }
  return archiveDownloaded ? 'data-saver' : 'nothing-downloaded'
}
