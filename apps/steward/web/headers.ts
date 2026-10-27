// The response headers Cloudflare Pages serves with the steward site, written
// into the build as `_headers` (vite.config.ts). The app signs people in and
// holds their access token in the browser, so the policy allows scripts from
// this site alone and network calls to exactly the hosts the app uses: the
// basemap, the Supabase project, and the steward API.

export const BASEMAP_ORIGIN = 'https://tiles.openfreemap.org'

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

export function contentSecurityPolicy(env: {
  supabaseUrl?: string
  apiUrl?: string
}): string {
  const connect = [
    "'self'",
    BASEMAP_ORIGIN,
    originOf(env.supabaseUrl),
    originOf(env.apiUrl),
  ]
  return [
    "default-src 'self'",
    "script-src 'self'",
    // React and MapLibre set element styles; the fonts' stylesheet is Google's.
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    'font-src https://fonts.gstatic.com',
    `img-src 'self' data: blob: ${BASEMAP_ORIGIN}`,
    `connect-src ${connect.filter(Boolean).join(' ')}`,
    // MapLibre's worker is a file Vite emits, so 'self'; blob: for its fallback.
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join('; ')
}

export function headersFile(env: { supabaseUrl?: string; apiUrl?: string }): string {
  return [
    '/*',
    `  Content-Security-Policy: ${contentSecurityPolicy(env)}`,
    '  X-Content-Type-Options: nosniff',
    '  Referrer-Policy: strict-origin-when-cross-origin',
    // Phase 4 (the camera and location at a site) will open camera and geolocation to 'self'.
    '  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()',
    '',
  ].join('\n')
}
