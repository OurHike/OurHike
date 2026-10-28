// The response headers Cloudflare Pages serves with the remediation site, written
// into the build as `_headers` (vite.config.ts). The app signs people in and
// holds their access token in the browser, so the policy allows scripts from
// this site alone and network calls to exactly the hosts the app uses: the
// basemap, the fonts and the Supabase project, which holds the remediation data
// and its photos (apps/remediation/db).

export const BASEMAP_ORIGIN = 'https://tiles.openfreemap.org'
/** Google Fonts: the stylesheet, and the font files it points at. */
export const FONT_ORIGINS = ['https://fonts.googleapis.com', 'https://fonts.gstatic.com']

/** The origin of an http(s) URL, or null for an empty or unusable one. */
export function originOf(url: string | undefined): string | null {
  if (!url) return null
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'https:' || parsed.protocol === 'http:'
      ? parsed.origin
      : null
  } catch {
    return null
  }
}

export function contentSecurityPolicy(env: { supabaseUrl?: string }): string {
  const supabase = originOf(env.supabaseUrl)
  const connect = [
    "'self'",
    BASEMAP_ORIGIN,
    // The service worker is served under this policy too, and fetches the
    // fonts to cache them: without these it could not, and the installed app
    // never had its fonts offline (the adversarial review's third pass, P5,
    // seen in Chromium, 2026-10-27).
    ...FONT_ORIGINS,
    supabase,
  ]
  return [
    "default-src 'self'",
    "script-src 'self'",
    // React and MapLibre set element styles; the fonts' stylesheet is Google's.
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    'font-src https://fonts.gstatic.com',
    // Claim photos are public objects in the project's Storage (#1910).
    ['img-src', "'self'", 'data:', 'blob:', BASEMAP_ORIGIN, supabase]
      .filter(Boolean)
      .join(' '),
    `connect-src ${connect.filter(Boolean).join(' ')}`,
    // MapLibre's worker is a file Vite emits, so 'self'; blob: for its fallback.
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join('; ')
}

export function headersFile(env: { supabaseUrl?: string }): string {
  return [
    '/*',
    `  Content-Security-Policy: ${contentSecurityPolicy(env)}`,
    '  X-Content-Type-Options: nosniff',
    '  Referrer-Policy: strict-origin-when-cross-origin',
    // A claim's photos are taken through a file input, which needs no camera
    // permission; phase 4's live photo-point outline will open camera to 'self'.
    '  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()',
    '',
  ].join('\n')
}
