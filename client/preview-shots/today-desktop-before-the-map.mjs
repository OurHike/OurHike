// Today on a laptop in the second before the map arrives (#1560): the
// sidebar, the journal in the column it will keep, and the pane the map is
// about to fill.
//
// WHAT THIS SHOT IS EVIDENCE FOR. Two things the settled desktop shot
// (today-desktop.mjs) cannot show, because both happen before it. The
// journal used to draw at the full width of the pane here and snap to its
// 404px column when MapScreen took it over - App.css's phone rule
// `.app__screen > :first-child { flex: 1 }` beat the column rule on
// specificity - and the whole page, sidebar included, used to go blank
// between the archive store answering and MapScreen's chunk landing, because
// on a laptop the tab bar lives inside that deferred screen. Measured
// 2026-09-17 on a cold cache at 1728x1080: 1,519 px then 405 px; the sidebar
// gone at 897 ms and back at 2,044 ms.
//
// WHAT TO LOOK FOR: the sidebar with Today selected, beside it a journal
// column of the same width as today-desktop.mjs's, and to the right an empty
// pane in the page colour - no map, no legend, no plate. Nothing else. That
// frame is the change: before it, this moment was either a journal the width
// of the window or no page at all.
//
// HOW THE CAMERA REACHES A FRAME THE LAUNCH PASSES THROUGH. `before` runs
// ahead of the app loading and holds MapScreen's chunk at the network for
// the life of the page, so the launch stays in its pre-map branch for as long
// as the shot takes. The pattern matches the built chunk (`assets/
// MapScreen-<hash>.js`), which is what the preview photographs; the dev
// server's module URL is matched too so `screenshot.mjs` can take the same
// frame by hand against either.
//
// Nobody's data: no account, no saved hikes, no reports or photos, no
// location - the journal is the empty install's own.

export const caption =
  'Today on a laptop before the map has arrived — the journal already in its column, the sidebar still there, the pane waiting (#1560)'
export const alt =
  'A wide browser window with the OurHike sidebar down the left and Today selected, a journal column beside it headed Today with the Nothing planned today card, and to the right of the column an empty pane in the page colour where the map will draw'

// The wide layout, which is the entire subject.
export const desktop = true

export async function before(page) {
  await page.route(
    /\/(src\/chrome\/MapScreen\.tsx|assets\/MapScreen-[^/]+\.js)(\?.*)?$/,
    () => new Promise(() => {}),
  )
}
