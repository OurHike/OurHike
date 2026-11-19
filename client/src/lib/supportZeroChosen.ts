// The moment a hiker keeps $0, as a window event (#1876, counted on #1902's
// usage measurement).
//
// lib/support.ts `writeZeroChoice` fires it; lib/useUsageMeasurement.ts
// listens, and queues one `support_chosen` row at $0 - the maintainer's "$0
// when chosen" (poll 2026-10-27). A leaf of its own so neither side imports
// the other: measurement is loaded behind import() and must not pull the
// support code into its chunk, and the support code must not pull the
// measurement registry into the first frame.
//
// Fired on this window only, never through `storage`: another tab hearing it
// would count one answer twice.
export const ZERO_CHOSEN = 'ourhike:support-zero-chosen'
