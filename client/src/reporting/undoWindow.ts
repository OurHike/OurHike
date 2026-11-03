// The one number the shell reads out of the report window, in a module of
// its own so the shell does not carry the window with it.
//
// features/LAUNCH_BUDGET.md §4.4: a static value import puts the exporting
// module in the importer's chunk whole - the bundler cannot take the number
// and leave the file - so `App.tsx` reading UNDO_WINDOW_MS out of
// ReportWindow.tsx held the window, its tiles, its icons and its categories
// in the eager closure. Measured against `check:build` on 2026-09-17: the
// window's #1563 growth put the eager total at 256,121 bytes in CI against a
// 256,000 budget (commit 53315108), and deferring only the window's sheet
// and reporter block left 232 bytes of headroom locally, less than the
// ~400 bytes by which CI's build runs larger than this sandbox's. The window
// is deferred now (screens/deferred.ts), and this file is what lets it be.

/**
 * How long a filed report can still be taken back.
 *
 * @unvalidated - eight seconds is the design handoff's number and nobody has
 * watched a hiker use it. What bounds the cost of it being wrong is that both
 * errors are recoverable: too short and the report stands, editable from the
 * outbox; too long and it sends a few seconds later than it might have, on a
 * queue whose ordinary delay is measured in hours. lib/outbox.ts's
 * MAX_UNDO_HOLD_MS is the ceiling any future value has to stay under.
 */
export const UNDO_WINDOW_MS = 8_000
