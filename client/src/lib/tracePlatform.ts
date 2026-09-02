// What the trace was recorded ON, so two files from two phones are separable
// (#1193).
//
// Nothing in an exported trace currently says which device produced it. That
// was survivable while one person walked one phone; it stops being survivable
// the moment the same maintainer field-tests an Android and an iPhone, which
// is exactly what #1193's CI builds are for. Two traces with different
// accuracy distributions and no column telling them apart is not a comparison,
// it is a pile.
//
// TWO FACTS, NOT ONE, and for the same reason `accuracy_m` and
// `accuracy_confidence` are two columns rather than a converted number: they
// answer different questions and collapsing them loses the one you did not
// think of.
//
//   `shell`     - which runtime the app is running inside: a Capacitor
//                 Android build, a Capacitor iOS build, or a browser. This is
//                 NOT what `fix_source` says. A native shell still produces
//                 `web` fixes when the background switch is off, so a file
//                 full of `web` rows could be either, and the difference
//                 decides how to read every gap in it - a browser tab gets
//                 suspended by the OS in ways an installed app does not.
//   `device_os` - which phone, whatever the shell. The whole point when the
//                 field testing happens through the PR preview, where BOTH
//                 phones report a shell of `web`.
//
// `device_os` IS A USER-AGENT SNIFF, and it is the weakest evidence in this
// file. It is here to label rows, and nothing anywhere may branch behaviour on
// it - a sniff that only sorts data is a convenience, one that picks a code
// path is a bug farm with a long tail. It answers null rather than guessing:
// an iPad in desktop mode reports as a Macintosh and gets null, which is the
// correct answer to "which of the two phones is this" when it is neither.

import { Capacitor } from '@capacitor/core'

/** Which runtime produced the trace. `web` covers every browser, installed to
 *  the home screen or not - the PWA is not a distinct runtime here, and
 *  claiming it was would be inventing a distinction the platform does not
 *  make. */
export type TraceShell = 'ios' | 'android' | 'web'

/** Which phone, where the user agent says plainly. Null is a real answer and
 *  the common one on a desktop browser. */
export type TraceDeviceOs = 'ios' | 'android' | null

export function traceShell(): TraceShell {
  const platform = Capacitor.getPlatform()
  return platform === 'ios' || platform === 'android' ? platform : 'web'
}

/**
 * The phone behind the user agent, as far as the string is willing to say.
 *
 * Deliberately two patterns and a null, rather than a library. Every extra
 * case this could recognise is a device nobody is field-testing on, and the
 * cost of a wrong label in a file used to derive safety thresholds is higher
 * than the cost of an empty one.
 */
export function deviceOsFrom(userAgent: string): TraceDeviceOs {
  if (/iPhone|iPad|iPod/.test(userAgent)) return 'ios'
  // Checked second: an Android tablet's UA contains "Linux" and an iOS UA
  // never contains "Android", so the order only matters against a spoofed
  // string, where nothing here is reliable anyway.
  if (/Android/.test(userAgent)) return 'android'
  return null
}

export function traceDeviceOs(): TraceDeviceOs {
  if (typeof navigator === 'undefined') return null
  return deviceOsFrom(navigator.userAgent)
}
