// GET /clubs/central-park-throughikers/coverage - sections with no live role.
//
// The embed draws this as a recruiting line and never as an alarm, which is
// the whole reason the coverage badge is allowed on a public page at all: no
// hiker is told a section is unmaintained.
import { DEMO_COVERAGE, served } from '../../../../../../lib/demoApi'

export const prerender = true

export const GET = () => served(DEMO_COVERAGE)
