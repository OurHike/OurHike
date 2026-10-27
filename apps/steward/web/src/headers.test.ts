import { expect, it } from 'vitest'
import { contentSecurityPolicy, headersFile, originOf } from '../headers'

it('the policy lets the page call only the basemap, the fonts, the Supabase project and the steward API', () => {
  const csp = contentSecurityPolicy({
    supabaseUrl: 'https://abc.supabase.co',
    apiUrl: 'https://steward-api.example/v1/',
  })
  const connect = csp.split('; ').find((d) => d.startsWith('connect-src'))
  expect(connect).toBe(
    "connect-src 'self' https://tiles.openfreemap.org https://fonts.googleapis.com https://fonts.gstatic.com https://abc.supabase.co https://steward-api.example",
  )
  expect(csp).toContain("script-src 'self'")
  expect(csp).not.toMatch(/script-src[^;]*unsafe/)
  expect(csp).toContain("frame-ancestors 'none'")
})

it('a build with no accounts allows no account hosts', () => {
  const connect = contentSecurityPolicy({})
    .split('; ')
    .find((d) => d.startsWith('connect-src'))
  expect(connect).toBe(
    "connect-src 'self' https://tiles.openfreemap.org https://fonts.googleapis.com https://fonts.gstatic.com",
  )
})

it('the service worker, which runs under the same policy, may fetch the fonts it caches', () => {
  // The third pass's P5: connect-src left the font hosts out, so the worker's
  // fetch for its fonts cache failed and the installed app never had them offline.
  const connect = contentSecurityPolicy({})
    .split('; ')
    .find((d) => d.startsWith('connect-src'))!
  expect(connect).toContain('https://fonts.googleapis.com')
  expect(connect).toContain('https://fonts.gstatic.com')
})

it('originOf refuses anything that is not an http(s) address', () => {
  expect(originOf('javascript:alert(1)')).toBeNull()
  expect(originOf('not a url')).toBeNull()
  expect(originOf('https://a.example/path?q')).toBe('https://a.example')
})

it('the headers file applies to every path', () => {
  expect(headersFile({}).split('\n')[0]).toBe('/*')
})

it('the policy lets claim photos load from signed R2 URLs and nowhere else new', () => {
  const img = contentSecurityPolicy({})
    .split('; ')
    .find((d) => d.startsWith('img-src'))
  expect(img).toBe(
    "img-src 'self' data: blob: https://tiles.openfreemap.org https://*.r2.cloudflarestorage.com",
  )
})
