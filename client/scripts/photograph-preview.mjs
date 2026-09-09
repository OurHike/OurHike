// Photographs a pull request's preview: the shots its recipes point at.
//
//   node scripts/photograph-preview.mjs --dist --changed=/tmp/pr-files.txt
//   node scripts/photograph-preview.mjs preview-shots/legend.mjs
//
// WHY THIS EXISTS
//
// pr-preview.yml used to photograph the same two screens on every pull
// request — first run, and the trail screen just past it — which answers
// "does the app still come up" and never "what did this change" (#998). The
// app has no URL routing; every screen past load is in-memory state, so a
// camera that only ever loads a page can only ever photograph the landing
// screen. This runner is the part that can follow a change: each recipe in
// client/preview-shots/ drives the built app to one screen, and CI hands
// this script the pull request's file list so the recipes that pull request
// added or changed get photographed and lead the preview comment.
//
// screenshot.mjs stays the tool for one ad-hoc frame; this orchestrates
// many, and owns everything the comment needs to say about them — the
// manifest and the markdown block — so the workflow YAML carries wiring
// rather than prose. Everything decided before a browser opens is exported
// and asserted in src/test/photographPreview.test.ts, the same split
// screenshot.mjs made (its header says why).
//
// Each shot gets its own server and browser via capture(), sequentially.
// Deliberate, not an oversight: a recipe that writes IndexedDB or leaves a
// sheet open must not leak into the next shot's frame, and a fresh browser
// profile is the isolation that cannot be forgotten. The price is about six
// seconds a shot (measured 2026-08-25: 18.8s wall for three shots, agent
// sandbox, --dist) in a job already minutes long.
//
// EXIT CODE: 0 when at least one shot was taken — per-shot failures are
// reported inside the comment, where a reviewer will actually see them.
// 1 when nothing could be shot at all, which pr-preview.yml's
// continue-on-error turns into the comment's no-image line.

import {
  capture,
  slug,
  budgetVerdict,
  DEFAULT_OUT_DIR,
  DEFAULT_WAIT_MS,
  CAPTURE_SCALE,
  PHONE,
  DESKTOP,
} from './screenshot.mjs'
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { resolve, dirname, basename, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const CLIENT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..')

/** Where recipes live, relative to client/. The repo-relative form is what
 *  arrives in a pull request's file list. */
export const RECIPE_DIR = 'preview-shots'

/**
 * The two shots every pull request gets, recipe or none: first run, because a
 * branch that breaks the very first screen breaks everybody, and the trail
 * screen, because it is the app past that gate. Everything else is
 * photographed only when the pull request touches its recipe — the comment is
 * about this change, not a gallery of every screen anyone ever recorded.
 */
export const STANDING = ['first-run', 'trail-screen']

/**
 * Stands in for the preview's base URL inside comment.md. The shots are taken
 * before the deploy that mints the real URL — they travel inside it — so the
 * workflow substitutes this after `wrangler` reports where the upload went.
 */
export const PREVIEW_BASE_PLACEHOLDER = '__PREVIEW_BASE__'

/**
 * 320, not the 390 a 2x capture is designed to display at (screenshot.mjs,
 * CAPTURE_SCALE): two of those plus table padding overflow the ~830 px a
 * comment gets, and seeing two shots side by side is worth the few pixels.
 * Moved here verbatim from pr-preview.yml when the markup moved (#998).
 */
export const DISPLAY_WIDTH = 320

/**
 * The same arithmetic for a desktop shot, which is a different shape and so
 * cannot share the phone's number (#1084).
 *
 * A desktop recipe is captured at DESKTOP's 1280x800 and at scale 1, not
 * CAPTURE_SCALE's 2. Both halves are forced by the same two constraints the
 * phone's numbers came from. Sharpness: displayed at 640 a 1280-wide capture
 * is already 2x, which is what capturing a 390-wide phone at 2 buys. Bytes:
 * 1280x800 at scale 2 is 2560x1600, four times the pixels of the 743,012-byte
 * trail-screen frame screenshot.mjs measured, which would clear BYTE_BUDGET on
 * its own before anything went wrong.
 *
 * 640 rather than 320 because a desktop frame IS the wide layout - the sidebar
 * beside the map, the card beside the photograph - and at 320 the thing under
 * review is four millimetres across. It takes a whole row for the same reason.
 */
export const DESKTOP_DISPLAY_WIDTH = 640

/** What a desktop capture is worth per CSS pixel - see DESKTOP_DISPLAY_WIDTH
 *  for why it is not CAPTURE_SCALE. */
export const DESKTOP_CAPTURE_SCALE = 1

export function usage() {
  return [
    'usage: node scripts/photograph-preview.mjs [recipes...] [options]',
    '',
    '  recipes...       recipe files to photograph on top of the standing two,',
    '                   e.g. preview-shots/legend.mjs',
    '  --changed=FILE   newline-separated list of repo-relative paths a pull',
    '                   request touches (CI passes this); every recipe in it is',
    '                   photographed. Unreadable or absent: standing shots only.',
    '  --dist           photograph the BUILT app (what CI deploys) rather than',
    '                   the dev server — run `npm run build` first',
    '  --out=DIR        where the PNGs, manifest.json and comment.md go',
    '                   (default client/dist/__screenshot/)',
  ].join('\n')
}

/** Flags out of argv, screenshot.mjs's pattern. Positionals are recipe files. */
export function parseRunnerArgs(argv) {
  const flag = (name) => argv.includes(`--${name}`)
  const value = (name, fallback) => {
    const found = argv.find((arg) => arg.startsWith(`--${name}=`))
    return found === undefined ? fallback : found.slice(name.length + 3)
  }
  return {
    asked: argv.filter((arg) => !arg.startsWith('--')),
    dist: flag('dist'),
    changedFile: value('changed', undefined),
    outDir: value('out', DEFAULT_OUT_DIR),
  }
}

const isRecipePath = (path) => new RegExp(`^client/${RECIPE_DIR}/[^/]+\\.mjs$`).test(path)

/** `client/preview-shots/x.mjs` and `preview-shots/x.mjs` both mean the same
 *  file; capture() runs from client/, so client-relative is the one kept. */
const toClientRelative = (path) => path.replace(/^client\//, '')

/**
 * Which shots to take, in the order the comment shows them: the pull
 * request's own first, then the standing two.
 *
 * Pure, and `exists` is injectable, so the test can hold the decisions —
 * which paths count as recipes, deletions being skipped rather than errors,
 * the nudge — without a filesystem staged to match.
 *
 * `changed` is the pull request's file list (renames appear under both
 * names, so a moved recipe is photographed where it landed and skipped where
 * it was). `nudge` is true when the pull request changes client/src/ but
 * points the camera at nothing — the comment then says so, because a missing
 * feature shot should look missing rather than normal (#998).
 *
 * @param {{ changed?: string[], asked?: string[],
 *           exists?: (file: string) => boolean }} selection
 */
export function planShots({
  changed = [],
  asked = [],
  exists = (file) => existsSync(resolve(CLIENT_DIR, file)),
}) {
  const changedRecipes = changed.filter(isRecipePath).map(toClientRelative)
  const askedRecipes = asked.map(toClientRelative)
  const stray = askedRecipes.find((file) => !isRecipePath(`client/${file}`))
  if (stray !== undefined) {
    throw new Error(`${stray} is not a ${RECIPE_DIR}/*.mjs recipe\n\n${usage()}`)
  }

  const shots = []
  const skipped = []
  const seen = new Set()
  const add = (file, changedByThisPr) => {
    const name = slug(basename(file, '.mjs'))
    if (seen.has(name)) return
    seen.add(name)
    if (!exists(file)) {
      skipped.push({ name, file, reason: 'not in this tree — deleted, or never here' })
      return
    }
    shots.push({ name, file, changed: changedByThisPr })
  }

  for (const file of [...changedRecipes, ...askedRecipes]) add(file, true)
  for (const name of STANDING) add(`${RECIPE_DIR}/${name}.mjs`, false)

  return {
    shots,
    skipped,
    nudge:
      changed.some((path) => path.startsWith('client/src/')) &&
      changedRecipes.length === 0 &&
      asked.length === 0,
  }
}

/**
 * The recipe contract, checked at the door so a wrong shape fails as one
 * clear sentence in the comment rather than as a puzzling frame. Everything
 * optional except that what is present has the right type: `caption` (table
 * heading) falls back to the shot name, `alt` to the caption, `entry` keeps
 * first run on screen, `desktop` photographs the wide layout instead of the
 * phone, `wait` overrides the settle, and the default export is the drive —
 * absent for a screen the app opens on by itself.
 */
export function normaliseRecipe(module, name) {
  const wrong = (what, value) => {
    throw new Error(`recipe ${name}: ${what} (got ${typeof value})`)
  }
  const drive = module.default
  if (drive !== undefined && typeof drive !== 'function')
    wrong('the default export must be the drive function', drive)
  const caption = module.caption ?? name
  if (typeof caption !== 'string') wrong('caption must be a string', module.caption)
  const alt = module.alt ?? caption
  if (typeof alt !== 'string') wrong('alt must be a string', module.alt)
  const wait = module.wait ?? DEFAULT_WAIT_MS
  if (typeof wait !== 'number' || !Number.isFinite(wait))
    wrong('wait must be a number of milliseconds', module.wait)
  return {
    drive,
    caption,
    alt,
    entry: module.entry === true,
    desktop: module.desktop === true,
    wait,
  }
}

/** Into an HTML attribute (the img alt). */
export function escapeAttr(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** Into a markdown table cell, where a bare pipe ends the cell. */
export function escapeCell(text) {
  return String(text).replace(/\|/g, '\\|').replace(/\r?\n/g, ' ')
}

const imageCell = (shot) =>
  `<img src="${PREVIEW_BASE_PLACEHOLDER}/__screenshot/${shot.name}.png" ` +
  `width="${shot.desktop === true ? DESKTOP_DISPLAY_WIDTH : DISPLAY_WIDTH}" ` +
  `alt="${escapeAttr(shot.alt)}">`

/**
 * Tables of two — the most a comment's width holds (DISPLAY_WIDTH) — except
 * that a desktop shot takes a row to itself, because at DESKTOP_DISPLAY_WIDTH
 * two of them are twice what the comment has (#1084). Greedy rather than
 * grouped: a desktop shot ends the row it lands in, so a mixed set keeps its
 * order instead of being sorted into a phone half and a desktop half. The
 * order is what says which shot the pull request is about.
 */
function tables(shots) {
  const lines = []
  for (let i = 0; i < shots.length;) {
    const row =
      shots[i].desktop === true || shots[i + 1]?.desktop === true
        ? shots.slice(i, i + 1)
        : shots.slice(i, i + 2)
    i += row.length
    lines.push(
      `| ${row.map((shot) => escapeCell(shot.caption)).join(' | ')} |`,
      `| ${row.map(() => '---').join(' | ')} |`,
      `| ${row.map(imageCell).join(' | ')} |`,
      '',
    )
  }
  return lines
}

/**
 * The comment's image block, from what was (and was not) photographed. The
 * pull request's own shots lead; the standing two follow; a recipe that
 * could not drive is a visible sentence rather than a silently absent image,
 * because a drive that stopped working usually means the pull request moved
 * the thing it photographs.
 */
export function renderComment(results, { nudge = false } = {}) {
  const taken = results.filter((shot) => shot.error === undefined)
  const own = taken.filter((shot) => shot.changed)
  const standing = taken.filter((shot) => !shot.changed)
  const failed = results.filter((shot) => shot.error !== undefined)

  const lines = []
  if (own.length > 0) {
    lines.push('#### What this pull request changed', '')
    lines.push(...tables(own))
  }
  if (standing.length > 0) {
    if (own.length > 0) lines.push('#### The app, as every pull request shows it', '')
    lines.push(...tables(standing))
  }
  for (const shot of failed) {
    lines.push(
      `**The camera could not take \`${shot.name}\`** — ${shot.error}. ` +
        `Its recipe (\`${RECIPE_DIR}/${shot.name}.mjs\`) drives the app to ` +
        'what it photographs, so this usually means the pull request moved ' +
        'that. The job log has the trace.',
      '',
    )
  }
  if (nudge) {
    lines.push(
      '_This pull request changes `client/src/` and no shot above is its own. ' +
        `If the change is somewhere a hiker can see, add or touch a recipe ` +
        `under \`client/${RECIPE_DIR}/\` and the camera will follow it — ` +
        '`.claude/skills/pr-screenshot/SKILL.md` says how._',
      '',
    )
  }
  const sizes = taken.some((shot) => shot.desktop === true)
    ? `${PHONE.width}x${PHONE.height}, the wide ones at ${DESKTOP.width}x${DESKTOP.height},`
    : `${PHONE.width}x${PHONE.height}`
  lines.push(
    `Photographed from this build at ${sizes} and served ` +
      'by this preview - so they go when it does. The camera goes where ' +
      `\`client/${RECIPE_DIR}/\` points it: a recipe this pull request adds or ` +
      'changes is photographed automatically.',
  )
  return lines.join('\n')
}

/** The pull request's file list, one repo-relative path a line. Unreadable
 *  fails toward the standing shots — a preview with the wrong two pictures
 *  still beats a preview with none. */
function readChangedList(file) {
  if (file === undefined) return []
  try {
    return readFileSync(file, 'utf8').split(/\r?\n/).filter(Boolean)
  } catch (error) {
    console.warn(`Could not read ${file} (${error.message}) - standing shots only.`)
    return []
  }
}

async function loadRecipe(file) {
  const module = await import(pathToFileURL(resolve(CLIENT_DIR, file)).href)
  return normaliseRecipe(module, basename(file, '.mjs'))
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const options = parseRunnerArgs(process.argv.slice(2))
  const plan = planShots({
    changed: readChangedList(options.changedFile),
    asked: options.asked,
  })
  for (const skip of plan.skipped) {
    console.warn(`Skipping ${skip.file}: ${skip.reason}.`)
  }

  const results = []
  for (const shot of plan.shots) {
    console.log(`Photographing ${shot.name} (${shot.file})`)
    try {
      const recipe = await loadRecipe(shot.file)
      const { bytes } = await capture({
        name: shot.name,
        outDir: options.outDir,
        url: undefined,
        dist: options.dist,
        skipEntry: !recipe.entry,
        waitMs: recipe.wait,
        scale: recipe.desktop ? DESKTOP_CAPTURE_SCALE : CAPTURE_SCALE,
        fullPage: false,
        viewport: recipe.desktop ? DESKTOP : PHONE,
        drive: recipe.drive,
      })
      const verdict = budgetVerdict(bytes)
      console.log(`  ${verdict.message}`)
      results.push({
        ...shot,
        caption: recipe.caption,
        alt: recipe.alt,
        desktop: recipe.desktop,
        bytes,
        overBudget: verdict.overBudget,
      })
    } catch (error) {
      // One shot failing is that shot's news to carry, not the run's: the
      // sentence lands in the comment, the trace stays here.
      console.error(`  could not photograph ${shot.name}: ${error?.stack ?? error}`)
      const message = String(error?.message ?? error).split('\n')[0]
      results.push({ ...shot, caption: shot.name, alt: shot.name, error: message })
    }
  }

  if (!results.some((shot) => shot.error === undefined)) {
    console.error('No shot could be taken at all - not writing a comment block.')
    process.exit(1)
  }

  mkdirSync(options.outDir, { recursive: true })
  const manifest = {
    placeholder: PREVIEW_BASE_PLACEHOLDER,
    nudge: plan.nudge,
    shots: results,
  }
  writeFileSync(
    join(options.outDir, 'manifest.json'),
    `${JSON.stringify(manifest, null, 2)}\n`,
  )
  writeFileSync(join(options.outDir, 'comment.md'), `${renderComment(results, plan)}\n`)
  const failures = results.filter((shot) => shot.error !== undefined).length
  console.log(
    `Wrote ${join(options.outDir, 'comment.md')} - ${results.length} shots` +
      (failures > 0 ? `, ${failures} failed` : ''),
  )
}
