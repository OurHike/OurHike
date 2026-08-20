// The site's build - WEBSITE.md §7's decision, taken by the maintainer
// 2026-08-20 (#116): Astro, static output, deployed by the existing Pages
// workflow. The output is plain HTML and CSS; if Astro were ever abandoned,
// site/dist keeps working and can be replaced page by page (§7's own
// mitigation for value #8).
import { defineConfig } from 'astro/config'

export default defineConfig({
  // The apex - #733 settled the domain before this build existed, so it
  // stands up at ourhike.org from its first commit. Canonical URLs and any
  // future sitemap derive from this.
  site: 'https://ourhike.org',
  // Directory-per-page output (/get-the-app/index.html), because that is the
  // URL shape GitHub Pages serves without redirects.
  build: { format: 'directory' },
})
