import { test, expect, type Page } from '@playwright/test'
import { existsSync, readdirSync, statSync } from 'node:fs'
import { join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  serveMarketingSite,
  openSitePage,
} from '../preview-shots/fixtures/marketingSite.mjs'

/**
 * Every page of the marketing site, audited in a real browser at phone and
 * desktop width, in light and dark - the checks that would have failed on
 * #1663 - The /for-orgs/ pages are unreadable in dark mode and misaligned on
 * a phone, before a maintainer found it on their own phone.
 *
 * WHY THIS EXISTS. The four org pages shipped in #1547 with "seven recipes,
 * all desktop" and none of the site, and every check the branch had was
 * about words: copy tests, a placeholder test, a build. So the page went out
 * with four cards at 1.21:1 in dark mode, a logo touching the edge of the
 * phone, a form field in the browser's own styling and a hero tagline at
 * 3.18:1 over the photograph - all measured, none looked at. Each check below
 * is one of those, generalised to every page, so the next one fails here.
 *
 * WHAT THIS CANNOT SEE, said so nobody reads a green run as "the page looks
 * right": a header that is merely too tall, a sketch that reads as a broken
 * image, a blaze beside the wrong line. Those are judgement, and the shot
 * recipes (client/preview-shots/site-*.mjs) are how they reach a reviewer.
 *
 * THE SITE IS SERVED FROM site/dist through the camera's own fixture, so CI
 * must build it first - client-tests.yml's flow job does. A missing build is
 * a failure here, never a skip: a skipped audit is the gap this file closes.
 */

const SITE = fileURLToPath(new URL('../../site/', import.meta.url))

/** Every page the site builds from site/src/pages, as the path it serves at. */
function sitePages(): string[] {
  const root = join(SITE, 'src', 'pages')
  const walk = (dir: string): string[] =>
    readdirSync(dir).flatMap((name) => {
      const path = join(dir, name)
      if (statSync(path).isDirectory()) return walk(path)
      return path.endsWith('.astro') ? [path] : []
    })
  return (
    walk(root)
      .map((file) =>
        relative(root, file)
          .split(sep)
          .join('/')
          .replace(/\.astro$/, ''),
      )
      // `index` is its folder; everything is served with a trailing slash.
      .map((route) => `/${route.replace(/(^|\/)index$/, '')}/`.replace(/\/+/g, '/'))
      .sort()
  )
}

const PAGES = sitePages()
const SCHEMES = ['light', 'dark'] as const

/**
 * WCAG 2.1 AA: 4.5:1 for body text, 3:1 for large text (24px, or 18.66px
 * bold). Not a house number - the standard's, and the one #1663's
 * measurements were read against.
 */
const BODY_CONTRAST = 4.5
const LARGE_CONTRAST = 3
const LARGE_TEXT_PX = 24
const LARGE_BOLD_TEXT_PX = 18.66

/**
 * The closest any text may sit to a phone's edge. 12px rather than the 24px
 * gutter `.wrap` gives, because the hero's credit pill sits 12px in by
 * design (`.hero__credit`) and is the tightest deliberate inset on the site;
 * the defect this catches was 0px. Reasoned from the stylesheet, not from a
 * reading test - @unvalidated as a comfort threshold, sound as a floor.
 */
const MIN_EDGE_PX = 12

/**
 * A phone target: the handoff's own minimum (HANDOFF_README.md, Responsive:
 * "44–56px hit targets"), and Apple's. Inline links inside a sentence are
 * exempt, as WCAG 2.5.8 exempts them: a link word cannot be 44px tall
 * without breaking the line it sits in.
 */
const MIN_TARGET_PX = 44

/** iOS Safari zooms the page into any field set smaller than this on focus. */
const MIN_INPUT_PX = 16

test.beforeAll(() => {
  expect(
    existsSync(join(SITE, 'dist', 'index.html')),
    'site/dist is not built - run `npm ci && npm run build` in site/ first (CI does, in the flow job)',
  ).toBe(true)
})

async function open(page: Page, path: string, scheme: (typeof SCHEMES)[number]) {
  await page.emulateMedia({ colorScheme: scheme })
  await serveMarketingSite(page)
  await page.goto('/', { waitUntil: 'load' })
  await openSitePage(page, path)
  // Fonts decide every line break the geometry checks read.
  await page.evaluate(() => document.fonts.ready)
}

/**
 * The whole page in the viewport at once, width unchanged, so the element
 * stack under every run of text can be read with elementsFromPoint - the only
 * way to see a photograph that sits beside the text rather than above it in
 * the tree, as the org hero's does. Capped so a runaway page fails loudly
 * rather than asking for a 100,000px surface.
 */
async function wholePageInView(page: Page) {
  const width = page.viewportSize()!.width
  const height = await page.evaluate(() => document.documentElement.scrollHeight)
  await page.setViewportSize({ width, height: Math.min(height, 20_000) })
  await page.evaluate(() => window.scrollTo(0, 0))
  // Every picture decoded before a pixel is sampled. A resize can make the
  // browser pick another srcset candidate, and a photograph still loading
  // samples as the page colour behind it - which is how a first draft of
  // this file measured the hero's credit pill at 1.07:1.
  await page.evaluate(() =>
    Promise.all([...document.images].map((img) => img.decode().catch(() => undefined))),
  )
}

interface TextRun {
  text: string
  where: string
  ratio: number | null
  needs: number
  overImage: boolean
  /** `data-audit-run` on the element that owns the text, for sampling. */
  id: number
  box: { x: number; y: number; width: number; height: number }
}

/**
 * Every visible run of text with the ratio of its colour to what is behind
 * it. Solid backgrounds are resolved from the element stack under the run's
 * centre; a run with an image under it before any opaque background is
 * returned with `overImage` so the caller can sample the pixels instead.
 */
async function textRuns(page: Page): Promise<TextRun[]> {
  const thresholds = {
    bar: BODY_CONTRAST,
    lowBar: LARGE_CONTRAST,
    large: LARGE_TEXT_PX,
    largeBold: LARGE_BOLD_TEXT_PX,
  }
  return page.evaluate(({ bar, lowBar, large, largeBold }) => {
    const parse = (value: string) => {
      const m = value.match(/rgba?\(([^)]+)\)/)
      if (!m) return null
      const parts = m[1]
        .split(/[\s,/]+/)
        .filter(Boolean)
        .map(Number)
      return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 }
    }
    const lin = (c: number) => {
      const v = c / 255
      return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
    }
    const lum = (c: { r: number; g: number; b: number }) =>
      0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b)
    const blend = (
      top: { r: number; g: number; b: number; a: number },
      under: { r: number; g: number; b: number },
    ) => ({
      r: top.r * top.a + under.r * (1 - top.a),
      g: top.g * top.a + under.g * (1 - top.a),
      b: top.b * top.a + under.b * (1 - top.a),
    })
    const describe = (el: Element) =>
      el.tagName.toLowerCase() +
      (el.id ? `#${el.id}` : '') +
      (typeof el.className === 'string' && el.className
        ? '.' + el.className.trim().split(/\s+/).join('.')
        : '')

    const runs: TextRun[] = []
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    const seen = new Set<Element>()
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const el = node.parentElement
      if (!el || seen.has(el) || !node.textContent?.trim()) continue
      seen.add(el)
      if (
        el.closest('[aria-hidden="true"], [hidden], [disabled], script, style, noscript')
      )
        continue
      const style = getComputedStyle(el)
      if (style.visibility !== 'visible' || Number(style.opacity) === 0) continue
      const range = document.createRange()
      range.selectNodeContents(node)
      const rect = range.getBoundingClientRect()
      if (rect.width < 1 || rect.height < 1) continue
      // Visually hidden on purpose: the skip link until focused (its own
      // test below), anything parked off-screen for a screen reader.
      if (rect.bottom < 0 || rect.right < 0 || el.closest('.skip')) continue

      const colour = parse(style.color)
      if (!colour) continue
      const size = parseFloat(style.fontSize)
      const bold = Number(style.fontWeight) >= 700
      const needs = size >= large || (bold && size >= largeBold) ? lowBar : bar

      // What is under the run, top layer first: an image-ish layer (an
      // <img>, a background-image) met before an opaque colour means the
      // background is pixels, and the caller samples them instead.
      let under = { r: 255, g: 255, b: 255 }
      let overImage = false
      const stack: { r: number; g: number; b: number; a: number }[] = []
      const layers = document.elementsFromPoint(
        rect.left + rect.width / 2,
        rect.top + rect.height / 2,
      )
      for (const layer of layers) {
        const ls = getComputedStyle(layer)
        const picture =
          ['IMG', 'PICTURE', 'VIDEO', 'CANVAS'].includes(layer.tagName) ||
          /url\(/.test(ls.backgroundImage)
        if (picture) {
          overImage = true
          break
        }
        const bg = parse(ls.backgroundColor)
        if (bg && bg.a > 0) {
          stack.push(bg)
          if (bg.a >= 1) break
        }
      }
      if (!overImage) {
        const page = parse(getComputedStyle(document.documentElement).backgroundColor)
        const bodyBg = parse(getComputedStyle(document.body).backgroundColor)
        const base =
          bodyBg && bodyBg.a > 0
            ? bodyBg
            : page && page.a > 0
              ? page
              : { r: 255, g: 255, b: 255, a: 1 }
        under = { r: base.r, g: base.g, b: base.b }
        for (const bg of stack.reverse()) under = blend(bg, under)
      }
      const fg = blend(colour, under)
      const [hi, lo] = [lum(fg), lum(under)].sort((x, y) => y - x)
      el.setAttribute('data-audit-run', String(runs.length))
      runs.push({
        id: runs.length,
        text: node.textContent.trim().slice(0, 60),
        where: describe(el),
        ratio: overImage ? null : Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100,
        needs,
        overImage,
        box: { x: rect.left, y: rect.top, width: rect.width, height: rect.height },
      })
    }
    return runs
  }, thresholds)
}

/**
 * Contrast for text over a photograph, by sampling the pixels behind it: the
 * text is made transparent, its box photographed, and the run's colour held
 * against the 90th-percentile brightest (or darkest) pixel - the method
 * #1663's 3.18:1 / 2.06:1 hero figures came from.
 */
async function sampledRatio(page: Page, run: TextRun): Promise<number> {
  // The element that owns the text, by the mark textRuns left on it - not
  // whatever is topmost at the run's centre. At 1280px the ridge's SVG box
  // sits over the credit pill (its painted shape stays below it), and a
  // first draft that hid "the element at the point" hid the ridge, sampled
  // the pill's own white letters and reported 1.07:1.
  const el = await page.$(`[data-audit-run="${run.id}"]`)
  if (el === null) return Infinity
  const colour = await el.evaluate((node) => getComputedStyle(node as Element).color)
  await el.evaluate((node) => ((node as HTMLElement).style.color = 'transparent'))
  const shot = await page.screenshot({
    clip: {
      x: run.box.x,
      y: run.box.y,
      width: Math.max(1, run.box.width),
      height: Math.max(1, run.box.height),
    },
    fullPage: true,
  })
  await el.evaluate((node) => ((node as HTMLElement).style.color = ''))
  return page.evaluate(
    async ({ png, colour }) => {
      const img = new Image()
      img.src = `data:image/png;base64,${png}`
      await img.decode()
      const canvas = document.createElement('canvas')
      canvas.width = img.width
      canvas.height = img.height
      const ctx = canvas.getContext('2d')!
      ctx.drawImage(img, 0, 0)
      const data = ctx.getImageData(0, 0, img.width, img.height).data
      const lin = (c: number) => {
        const v = c / 255
        return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
      }
      const lum = (r: number, g: number, b: number) =>
        0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
      const [r, g, b] = (colour.match(/[\d.]+/g) ?? ['0', '0', '0']).map(Number)
      const fg = lum(r, g, b)
      const ratios: number[] = []
      for (let i = 0; i < data.length; i += 4) {
        const bg = lum(data[i], data[i + 1], data[i + 2])
        const [hi, lo] = [fg, bg].sort((x, y) => y - x)
        ratios.push((hi + 0.05) / (lo + 0.05))
      }
      ratios.sort((x, y) => x - y)
      // The worst tenth of the background: a word over one bright cloud
      // is still a word somebody has to read.
      return Math.round(ratios[Math.floor(ratios.length * 0.1)] * 100) / 100
    },
    { png: shot.toString('base64'), colour },
  )
}

/**
 * Every photo credit something paints over, by pixels rather than hit
 * testing. The credit is photographed, its whole ancestor chain is lifted to
 * the top of the page's stacking order, and it is photographed again: if
 * anything was drawn over it, the two frames differ.
 *
 * Pixels, because hit testing answers a different question. An inline SVG's
 * box is hit-testable even where it paints nothing - at 1280px the ridge's
 * box overlaps the credit while its shape stays below it - and a
 * pointer-events: none layer is invisible to it while painting on top. The
 * credit is a licence condition (client/src/lib/heroPhotos.ts), and #1663's
 * own first build covered it with the ridge it had just made visible.
 */
async function coveredCredits(page: Page): Promise<string[]> {
  const covered: string[] = []
  const credits = page.locator('.hero__credit')
  for (let i = 0; i < (await credits.count()); i += 1) {
    const credit = credits.nth(i)
    await credit.scrollIntoViewIfNeeded()
    const before = await credit.screenshot()
    await credit.evaluate((node) => {
      for (let a: HTMLElement | null = node as HTMLElement; a; a = a.parentElement) {
        a.dataset.auditZ = a.style.zIndex
        if (getComputedStyle(a).position !== 'static') a.style.zIndex = '2147483647'
      }
    })
    const after = await credit.screenshot()
    await credit.evaluate((node) => {
      for (let a: HTMLElement | null = node as HTMLElement; a; a = a.parentElement) {
        a.style.zIndex = a.dataset.auditZ ?? ''
        delete a.dataset.auditZ
      }
    })
    const changed = await page.evaluate(
      async ({ one, two }) => {
        const pixels = async (png: string) => {
          const img = new Image()
          img.src = `data:image/png;base64,${png}`
          await img.decode()
          const canvas = document.createElement('canvas')
          canvas.width = img.width
          canvas.height = img.height
          const ctx = canvas.getContext('2d')!
          ctx.drawImage(img, 0, 0)
          return ctx.getImageData(0, 0, img.width, img.height).data
        }
        const [a, b] = [await pixels(one), await pixels(two)]
        let differ = 0
        for (let p = 0; p < a.length; p += 4) {
          const d = Math.max(
            Math.abs(a[p] - b[p]),
            Math.abs(a[p + 1] - b[p + 1]),
            Math.abs(a[p + 2] - b[p + 2]),
          )
          if (d > 24) differ += 1
        }
        return differ / (a.length / 4)
      },
      { one: before.toString('base64'), two: after.toString('base64') },
    )
    // Measured 2026-09-26 against the built /for-orgs/: this branch changes
    // 0.0% of the pill's pixels at 390px and at 1280px; the same build with
    // the credit put back at `bottom: 12px`, under the ridge, changes 4.7%
    // at 390px and 13.1% at 1280px. 1% sits clear of both.
    if (changed > 0.01) {
      covered.push(
        `${Math.round(changed * 100)}% of "${(await credit.textContent())?.trim()}" is under another layer`,
      )
    }
  }
  return covered
}

async function contrastFailures(page: Page): Promise<string[]> {
  await wholePageInView(page)
  const failures: string[] = []
  for (const run of await textRuns(page)) {
    const ratio = run.overImage ? await sampledRatio(page, run) : run.ratio!
    if (ratio < run.needs)
      failures.push(`${ratio}:1 < ${run.needs}:1  ${run.where}  "${run.text}"`)
  }
  return failures
}

for (const path of PAGES) {
  for (const scheme of SCHEMES) {
    test.describe(`${path} in ${scheme}`, () => {
      test('every run of text reaches WCAG AA contrast on a phone', async ({ page }) => {
        await open(page, path, scheme)
        expect(await contrastFailures(page), 'text below WCAG AA contrast').toEqual([])
      })

      test('every run of text reaches WCAG AA contrast on a desktop @desktop', async ({
        page,
      }) => {
        await open(page, path, scheme)
        expect(await contrastFailures(page), 'text below WCAG AA contrast').toEqual([])
      })

      test('shows a readable skip link when it takes focus', async ({ page }) => {
        await open(page, path, scheme)
        await page.keyboard.press('Tab')
        const skip = page.locator('.skip')
        await expect(skip).toBeFocused()
        const ratio = await skip.evaluate((node) => {
          const parse = (v: string) => (v.match(/[\d.]+/g) ?? []).map(Number)
          const lin = (c: number) => {
            const v = c / 255
            return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
          }
          const lum = ([r, g, b]: number[]) =>
            0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
          const s = getComputedStyle(node)
          const [hi, lo] = [lum(parse(s.color)), lum(parse(s.backgroundColor))].sort(
            (x, y) => y - x,
          )
          return (hi + 0.05) / (lo + 0.05)
        })
        expect(ratio).toBeGreaterThanOrEqual(BODY_CONTRAST)
      })
    })
  }

  test.describe(path, () => {
    test('never scrolls sideways, and keeps text off the edge of a phone', async ({
      page,
    }) => {
      await open(page, path, 'light')
      const { scroll, width, crowded } = await page.evaluate((min) => {
        const vw = document.documentElement.clientWidth
        const scrolls = (el: Element) => {
          for (let a: Element | null = el; a; a = a.parentElement) {
            const o = getComputedStyle(a).overflowX
            if (o === 'auto' || o === 'scroll') return true
          }
          return false
        }
        const crowded: string[] = []
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
          const el = node.parentElement
          if (
            !el ||
            !node.textContent?.trim() ||
            el.closest('.skip, [hidden], script, style')
          )
            continue
          const range = document.createRange()
          range.selectNodeContents(node)
          const r = range.getBoundingClientRect()
          if (r.width < 1 || scrolls(el)) continue
          if (r.left < min || r.right > vw - min) {
            crowded.push(
              `${Math.round(r.left)}..${Math.round(r.right)} of ${vw}  "${node.textContent.trim().slice(0, 40)}"`,
            )
          }
        }
        return { scroll: document.documentElement.scrollWidth, width: vw, crowded }
      }, MIN_EDGE_PX)
      expect(scroll, 'the page scrolls sideways').toBeLessThanOrEqual(width)
      expect(crowded, `text closer than ${MIN_EDGE_PX}px to the phone's edge`).toEqual([])
    })

    test('gives every control a phone-sized target, a 16px field and the site’s own styling', async ({
      page,
    }) => {
      await open(page, path, 'light')
      const problems = await page.evaluate(
        ({ minTarget, minInput }) => {
          const out: string[] = []
          const name = (el: Element) =>
            (
              el.textContent?.trim() ||
              el.getAttribute('aria-label') ||
              el.getAttribute('placeholder') ||
              el.tagName
            ).slice(0, 40)
          const inSentence = (el: Element) => {
            const parent = el.parentElement
            if (!parent || getComputedStyle(el).display !== 'inline') return false
            return [...parent.childNodes].some(
              (n) =>
                n !== el &&
                n.nodeType === Node.TEXT_NODE &&
                n.textContent!.trim().length > 0,
            )
          }
          const SITE_FONTS = /Public Sans|IBM Plex Mono|Bitter/
          for (const el of document.querySelectorAll(
            'a[href], button, input, select, textarea, summary',
          )) {
            const r = el.getBoundingClientRect()
            const s = getComputedStyle(el)
            if (
              r.width < 1 ||
              s.visibility !== 'visible' ||
              el.closest('.skip, [hidden]')
            )
              continue
            // The embed widgets are exempt from the size check alone: they
            // render on organizations' own sites, so resizing them is a
            // product decision - #1671, The embed widgets' controls are
            // 19–37px tall on a phone. Drop this when that closes.
            const embedded = el.closest('[id^="ourhike-"]') !== null
            if (!embedded && !inSentence(el) && r.height < minTarget)
              out.push(
                `${Math.round(r.height)}px tall target  ${el.tagName.toLowerCase()} "${name(el)}"`,
              )
            if (
              ['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName) &&
              parseFloat(s.fontSize) < minInput
            )
              out.push(`${s.fontSize} field  "${name(el)}"`)
            if (['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName)) {
              if (!SITE_FONTS.test(s.fontFamily))
                out.push(
                  `browser font (${s.fontFamily})  ${el.tagName.toLowerCase()} "${name(el)}"`,
                )
              for (const side of ['Top', 'Right', 'Bottom', 'Left']) {
                const style = s.getPropertyValue(`border-${side.toLowerCase()}-style`)
                if (style === 'outset' || style === 'inset') {
                  out.push(
                    `browser ${style} border  ${el.tagName.toLowerCase()} "${name(el)}"`,
                  )
                  break
                }
              }
            }
          }
          return out
        },
        { minTarget: MIN_TARGET_PX, minInput: MIN_INPUT_PX },
      )
      expect(problems).toEqual([])
    })

    test('never covers a photograph’s credit on a phone', async ({ page }) => {
      await open(page, path, 'light')
      expect(await coveredCredits(page), 'painted over a photo credit').toEqual([])
    })

    test('never covers a photograph’s credit on a desktop @desktop', async ({ page }) => {
      await open(page, path, 'light')
      expect(await coveredCredits(page), 'painted over a photo credit').toEqual([])
    })
  })
}
