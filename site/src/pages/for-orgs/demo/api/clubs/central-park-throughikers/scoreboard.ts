// GET /clubs/central-park-throughikers/scoreboard - the coverage badge's
// three figures, in the shape the real API serves them.
//
// The badge read `/coverage` until 2026-09-18, which the real API gates to
// admins and supervisors - so it drew nothing on every real site and only ever
// appeared to work here, where a fixture answers without auth. The coverage
// report is right to be gated; pointing a PUBLIC embed at it was the mistake.
import { DEMO_SCOREBOARD, served } from '../../../../../../lib/demoApi'

export const prerender = true

export const GET = () => served(DEMO_SCOREBOARD)
