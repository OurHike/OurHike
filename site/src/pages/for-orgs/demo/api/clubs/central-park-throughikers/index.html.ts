// GET /clubs/central-park-throughikers - the org itself.
//
// WRITTEN AS THAT DIRECTORY'S INDEX, which is the one shape concession these
// endpoints make to being files. The real API answers both
// `/clubs/{slug}` and `/clubs/{slug}/registry`, and a filesystem cannot hold
// the same name as a file and a directory at once - Astro fails the build
// with EISDIR if you ask it to. A static host serves `/clubs/{slug}` from
// `/clubs/{slug}/index.html`, so the path the embed requests is the path it
// gets, and the sibling reads keep their own names.
//
// The `.html` in the filename is what puts it there; the bytes are JSON and
// `ourhike.js` reads them with `JSON.parse(request.responseText)`, which does
// not consult the content type.
import { DEMO_ORG, served } from '../../../../../../lib/demoApi'

export const prerender = true

export const GET = () => served(DEMO_ORG)
