// GET /clubs/central-park-throughikers/registry - parks, trails and sections,
// which is what the hikes embed draws its table from.
import { DEMO_REGISTRY, served } from '../../../../../../lib/demoApi'

export const prerender = true

export const GET = () => served(DEMO_REGISTRY)
