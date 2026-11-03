// GET /workdays?org=central-park-throughikers&days=60
//
// The query string is ignored, and that is the one place these endpoints are
// thinner than the API they stand in for: a static file cannot vary by
// parameter. The demo's workdays are all inside the 60-day window the page
// asks for, so the answer is the same one the real endpoint would give.
import { DEMO_WORKDAYS, served } from '../../../../lib/demoApi'

export const prerender = true

export const GET = () => served(DEMO_WORKDAYS)
