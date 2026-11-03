// The service worker's cache of claim photos (vite.config.ts), named here so
// signing out can empty it (src/account.tsx). No imports: vite.config.ts
// loads this file at build time.

/** Photos this phone has shown, kept for use with no signal. */
export const PHOTO_CACHE = 'claim-photos'

/**
 * A signed link to a photo in the remediation-photos bucket, on this build's
 * Supabase project. Anchored at the origin, because workbox matches a
 * cross-origin request only from the start of its address; with no project
 * configured it matches nothing.
 */
export function photoLinkPattern(supabaseUrl: string | undefined): RegExp {
  if (!supabaseUrl) return /$^/
  const origin = new URL(supabaseUrl).origin.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&')
  return new RegExp(`^${origin}\\/storage\\/v1\\/object\\/sign\\/remediation-photos\\/`)
}
