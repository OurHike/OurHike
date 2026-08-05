// Formats a byte count the way WIREFRAMES.md quotes the download sizes:
// "64 MB", "314 MB", "1.18 GB".
//
// Decimal (SI) units, not binary. pipeline/README.md measured these figures
// against decimal MB/GB, and rendering 314 MB as "299 MiB" would not match the
// number anyone has been shown - these sizes get weighed against remaining
// phone storage before a thru hike, so they need to agree everywhere.

const MB = 1_000_000
const GB = 1_000_000_000

/** Trims "1.20" to "1.2" and "2.00" to "2" without touching "1.18".
 *
 *  Anchored to a decimal point rather than stripping trailing zeros outright:
 *  a bare "10" must come back as "10", not "1". The previous version guarded
 *  that with an `includes('.')` check, which read as defensive but was dead -
 *  both callers arrive via toFixed(), which always yields a point - so the
 *  case it protected against could never be observed and the guard could not
 *  be tested. Handling it in the pattern makes the function safe for any
 *  string AND leaves nothing unreachable behind it. */
function trimZeros(value: string): string {
  return value.replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '')
}

export function formatBytes(bytes: number): string {
  if (bytes >= GB) return `${trimZeros((bytes / GB).toFixed(2))} GB`
  return `${trimZeros((bytes / MB).toFixed(1))} MB`
}

/** For the counter that re-renders on every received chunk. formatBytes made
 *  it flicker, but only below a gigabyte: the MB tenths digit spins faster
 *  than anyone can read, and trimming "10.0" to "10" changed the string's
 *  width mid-download, so the whole line jumped. So megabytes lose their
 *  decimal here. Gigabytes keep both of theirs - a hundredth of a GB ticks
 *  only every 10 MB, which reads calmly, and a download that counted whole
 *  gigabytes would look stalled for its final stretch - but pinned, never
 *  trimmed: "1.10 GB" holds the width "1.18 GB" needs.
 *
 *  Everything floors rather than rounds. A counter that overstates reads as a
 *  lie the moment it stalls ("314 MB of 314 MB" while failed), and flooring
 *  also caps the string at the total's own width - 999 MB never becomes
 *  "1000 MB" - which is what lets the caller reserve that width exactly. */
export function formatBytesLive(bytes: number): string {
  if (bytes >= GB) return `${(Math.floor((bytes / GB) * 100) / 100).toFixed(2)} GB`
  return `${Math.floor(bytes / MB)} MB`
}
