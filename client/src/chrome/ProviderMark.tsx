// The mark on each sign-in door (#1572): Google's G, GitHub's mark, and
// OurHike's own blaze on the email button.
//
// Each provider's guidelines are the reason these are drawn here rather
// than left to a label:
//
//   Google - developers.google.com/identity/branding-guidelines, read
//   2026-09-17: the standard multicolour "G" (never monochrome, never
//   redrawn), on a light, dark or neutral button, with "Continue with
//   Google" as one of the three approved labels. The four paths below are
//   the G as Google's own g-logo asset draws it, in its four brand colours
//   (#EA4335, #4285F4, #FBBC05, #34A853). They were not byte-compared
//   against a download from that page, so what backs them is the frame in
//   the pull request that added them.
//
//   GitHub - brand.github.com/foundations/logo, read 2026-09-17: the mark
//   in black or white at the highest contrast available, no effects, never
//   on a busy background. The path is primer/octicons' mark-github-16.svg,
//   fetched from the repository the same day; `currentColor` is what lets
//   one path be white on the black button and black on the white one
//   (screens/reporting.css).
//
//   Apple - deferred with the provider (#92). Apple's button has its own
//   Human Interface Guidelines and its own logo asset, and this project
//   holds neither, so nothing is drawn: something Apple-shaped made here
//   would be exactly the "create your own icon" each of these pages forbids.
//
//   Email - OurHike's own door, so OurHike's own mark: the app icon
//   chrome/TabBar.tsx already draws, from design-system/assets/logo-icon.svg.
//
// Every mark is decorative. A button's accessible name is its label - what
// the tests and e2e/identityRooms.spec.ts find it by - so the SVGs are
// aria-hidden and the image has an empty alt.

import logoIcon from '../design-system/assets/logo-icon.svg'
import type { AuthProvider } from '../screens/SignInPrompt'

/** The class every mark carries; screens/reporting.css sizes it. */
export const MARK_CLASS = 'reporting__provider-mark'

export function ProviderMark({ provider }: { provider: AuthProvider }) {
  switch (provider) {
    case 'google':
      return (
        <svg
          className={MARK_CLASS}
          viewBox="0 0 48 48"
          aria-hidden="true"
          focusable="false"
        >
          <path
            fill="#EA4335"
            d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
          />
          <path
            fill="#4285F4"
            d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
          />
          <path
            fill="#FBBC05"
            d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
          />
          <path
            fill="#34A853"
            d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
          />
        </svg>
      )
    case 'github':
      return (
        <svg
          className={MARK_CLASS}
          viewBox="0 0 16 16"
          fill="currentColor"
          aria-hidden="true"
          focusable="false"
        >
          <path d="M6.766 11.328c-2.063-.25-3.516-1.734-3.516-3.656 0-.781.281-1.625.75-2.188-.203-.515-.172-1.609.063-2.062.625-.078 1.468.25 1.968.703.594-.187 1.219-.281 1.985-.281.765 0 1.39.094 1.953.265.484-.437 1.344-.765 1.969-.687.218.422.25 1.515.046 2.047.5.593.766 1.39.766 2.203 0 1.922-1.453 3.375-3.547 3.64.531.344.89 1.094.89 1.954v1.625c0 .468.391.734.86.547C13.781 14.359 16 11.53 16 8.03 16 3.61 12.406 0 7.984 0 3.563 0 0 3.61 0 8.031a7.88 7.88 0 0 0 5.172 7.422c.422.156.828-.125.828-.547v-1.25c-.219.094-.5.156-.75.156-1.031 0-1.64-.562-2.078-1.609-.172-.422-.36-.672-.719-.719-.187-.015-.25-.093-.25-.187 0-.188.313-.328.625-.328.453 0 .844.281 1.25.86.313.452.64.655 1.031.655s.641-.14 1-.5c.266-.265.47-.5.657-.656" />
        </svg>
      )
    case 'email':
      return <img className={MARK_CLASS} src={logoIcon} alt="" />
    case 'apple':
      return null
  }
}
