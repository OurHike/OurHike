// The guard gets a guard (#319).
//
// scripts/check-build-output.mjs is the only layer between the fully-mocked
// jsdom suite and a shipped artifact - it exists because of the blank-map
// worker-URL bug that 100% green tests structurally could not see. Until now
// it had no tests of its own: if its assertions rot, every layer past the
// unit suite is silently gone and nothing says so.
//
// Each case here runs the REAL script, as `npm run build` runs it, against a
// tiny synthetic dist/ tree built in test code (TESTING.md's synthetic-
// fixture rule) - and most cases assert it goes RED on one class of defect,
// which is the confirm-red-once rule applied to the guard itself. Spawning a
// node per case costs tens of milliseconds and buys the honest thing: the
// entry point that gates the build is the thing proven to fail.

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const SCRIPT = resolve(process.cwd(), 'scripts/check-build-output.mjs')
const WORKER = 'maplibre-gl-worker-abc123.js'
const GLYPH_RANGES = 256
const UI_FONT_FILES = 10

let dist: string

beforeEach(() => {
  dist = mkdtempSync(join(tmpdir(), 'check-build-output-'))
})

afterEach(() => {
  rmSync(dist, { recursive: true, force: true })
})

/** A minimal dist/ that satisfies every check - the baseline each defect
 *  case then breaks in exactly one way. */
function passingDist() {
  mkdirSync(join(dist, 'assets'), { recursive: true })
  mkdirSync(join(dist, 'glyphs'), { recursive: true })

  writeFileSync(join(dist, 'assets', WORKER), '// worker')
  writeFileSync(
    join(dist, 'assets', 'index-x.js'),
    `importScripts; new Worker('assets/${WORKER}')`,
  )
  writeFileSync(join(dist, 'index.html'), '<script src="assets/index-x.js"></script>')
  writeFileSync(
    join(dist, 'assets', 'index-x.css'),
    '.maplibregl-canvas{position:absolute}.maplibregl-ctrl-bottom-right{right:0}',
  )

  const glyphs: string[] = []
  for (let i = 0; i < GLYPH_RANGES; i++) {
    const name = `glyphs/UI/${i * 256}-${i * 256 + 255}.pbf`
    glyphs.push(name)
    if (i === 0) mkdirSync(join(dist, 'glyphs', 'UI'), { recursive: true })
    writeFileSync(join(dist, name), '')
  }

  const fonts: string[] = []
  for (let i = 0; i < UI_FONT_FILES; i++) {
    const name = `assets/font-${i}.woff2`
    fonts.push(name)
    writeFileSync(join(dist, name), '')
  }

  writeFileSync(
    join(dist, 'sw.js'),
    `self.__WB_MANIFEST = ${JSON.stringify([`assets/${WORKER}`, ...glyphs, ...fonts])}`,
  )
}

/** Runs the real script against the fixture; returns exit code and output. */
function runCheck(): { code: number; output: string } {
  try {
    const stdout = execFileSync(process.execPath, [SCRIPT], {
      env: { ...process.env, CHECK_BUILD_OUTPUT_DIST: dist },
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    return { code: 0, output: stdout }
  } catch (error) {
    const failed = error as { status: number | null; stdout: string; stderr: string }
    return { code: failed.status ?? -1, output: `${failed.stdout}\n${failed.stderr}` }
  }
}

describe('check-build-output.mjs', () => {
  it('passes a complete build', () => {
    passingDist()

    const { code, output } = runCheck()

    expect(output).toContain('Build output OK')
    expect(code).toBe(0)
  })

  it('fails when there is no build output at all', () => {
    rmSync(dist, { recursive: true, force: true })

    const { code, output } = runCheck()

    expect(code).toBe(1)
    expect(output).toContain('No build output')
  })

  it('fails on a referenced asset the build never emitted', () => {
    // The general shape of the blank-map bug: the app asks for a file the
    // build did not publish, and gets a 404 at runtime.
    passingDist()
    writeFileSync(
      join(dist, 'assets', 'index-x.js'),
      `new Worker('assets/${WORKER}'); fetch('assets/ghost-9f.js')`,
    )

    const { code, output } = runCheck()

    expect(code).toBe(1)
    expect(output).toContain('Referenced but never emitted: assets/ghost-9f.js')
  })

  it('fails when the worker is missing from the build entirely', () => {
    passingDist()
    rmSync(join(dist, 'assets', WORKER))
    // Drop the reference too - with it, this is the generic case above; the
    // named REQUIRED_ASSETS check exists for the build that stopped
    // mentioning the worker at all and so looks internally consistent.
    writeFileSync(join(dist, 'assets', 'index-x.js'), '// no worker anywhere')

    const { code, output } = runCheck()

    expect(code).toBe(1)
    expect(output).toContain("Missing from the build: MapLibre's web worker")
  })

  it('fails when the worker is emitted but nothing points at it', () => {
    // The silent-absence case the checker was written for: MapLibre falls
    // back to guessing a path next to the app chunk, where nothing is
    // published, and the map draws only its background colour.
    passingDist()
    writeFileSync(join(dist, 'assets', 'index-x.js'), '// reference gone')

    const { code, output } = runCheck()

    expect(code).toBe(1)
    expect(output).toContain('Emitted but never referenced')
  })

  it('fails when there is no service worker', () => {
    passingDist()
    rmSync(join(dist, 'sw.js'))

    const { code, output } = runCheck()

    expect(code).toBe(1)
    expect(output).toContain('No service worker in the build output.')
  })

  it('fails when the worker is not in the precache', () => {
    passingDist()
    writeFileSync(join(dist, 'sw.js'), 'self.__WB_MANIFEST = []')

    const { code, output } = runCheck()

    expect(code).toBe(1)
    expect(output).toContain('Not precached')
  })

  it('fails on a wrong glyph-range count', () => {
    // Per-range runtime failure: a build missing half the ranges labels an
    // English test session perfectly and drops labels in the field.
    passingDist()
    rmSync(join(dist, 'glyphs', 'UI', '0-255.pbf'))

    const { code, output } = runCheck()

    expect(code).toBe(1)
    expect(output).toContain(`Expected ${GLYPH_RANGES} glyph range files`)
  })

  it('fails when glyphs exist but are not precached', () => {
    passingDist()
    const sw = `self.__WB_MANIFEST = ${JSON.stringify([`assets/${WORKER}`])}`
    writeFileSync(join(dist, 'sw.js'), sw)

    const { code, output } = runCheck()

    expect(code).toBe(1)
    expect(output).toContain("glyph ranges are in the service worker's precache")
  })

  it('fails on a cross-origin @import in the built CSS', () => {
    // The #717 shape: a render-blocking request to somebody else's server,
    // missing exactly where this app is meant to work.
    passingDist()
    writeFileSync(
      join(dist, 'assets', 'index-x.css'),
      '@import "https://fonts.example.com/css";.maplibregl-canvas{position:absolute}.maplibregl-ctrl-bottom-right{right:0}',
    )

    const { code, output } = runCheck()

    expect(code).toBe(1)
    expect(output).toContain('Cross-origin reference in the built CSS')
  })

  it('fails on a wrong UI-font count', () => {
    passingDist()
    rmSync(join(dist, 'assets', 'font-0.woff2'))

    const { code, output } = runCheck()

    expect(code).toBe(1)
    expect(output).toContain(`Expected ${UI_FONT_FILES} self-hosted .woff2 files`)
  })

  it("fails when MapLibre's stylesheet rules never reached the bundle", () => {
    // No reference to look for - the import was simply never written - so
    // the checker reads the emitted CSS for rules only that file carries.
    passingDist()
    writeFileSync(join(dist, 'assets', 'index-x.css'), '.app{color:red}')

    const { code, output } = runCheck()

    expect(code).toBe(1)
    expect(output).toContain('Missing from the built CSS')
  })
})
