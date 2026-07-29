// Formats a byte count the way WIREFRAMES.md quotes the download sizes:
// "64 MB", "314 MB", "1.18 GB".
//
// Decimal (SI) units, not binary. pipeline/README.md measured these figures
// against decimal MB/GB, and rendering 314 MB as "299 MiB" would not match the
// number anyone has been shown - these sizes get weighed against remaining
// phone storage before a thru hike, so they need to agree everywhere.

const MB = 1_000_000
const GB = 1_000_000_000

/** Trims "1.20" to "1.2" and "2.00" to "2" without touching "1.18". */
function trimZeros(value: string): string {
  return value.includes('.') ? value.replace(/\.?0+$/, '') : value
}

export function formatBytes(bytes: number): string {
  if (bytes >= GB) return `${trimZeros((bytes / GB).toFixed(2))} GB`
  return `${trimZeros((bytes / MB).toFixed(1))} MB`
}
