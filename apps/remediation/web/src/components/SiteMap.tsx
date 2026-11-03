import { useEffect, useRef } from 'react'
import type { FeatureCollection } from 'geojson'
import type { Map as MapLibreMap, StyleSpecification } from 'maplibre-gl'
import { USE_FIXTURES } from '../data'
import type { Site } from '../types'

/** OpenFreeMap's free OpenStreetMap vector tiles: no key, full zoom (PLAN.md §3). */
const BASEMAP = 'https://tiles.openfreemap.org/styles/liberty'

/** The invented sites sit in the open sea, so they get a plain ground rather than a basemap of water. */
const PLAIN: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    { id: 'ground', type: 'background', paint: { 'background-color': '#e8ede6' } },
  ],
}

function asGeoJson(sites: Site[]): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: sites.map((s) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
      properties: {
        id: s.rims_id,
        tier: s.tier ?? 'none',
        official: s.site_type !== 'User Created Campsite',
      },
    })),
  }
}

interface Props {
  sites: Site[]
  onSelect?: (site: Site) => void
  /** Zoom to these sites whenever they change. */
  fit?: boolean
}

/**
 * The sites as dots coloured by tier: P1 flagging-tape orange, P2 amber, P3 sage, the rest grey.
 * MapLibre is loaded on first use, so a test or a page without a map never pays for it.
 */
export function SiteMap({ sites, onSelect, fit = true }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const map = useRef<MapLibreMap | null>(null)
  const latest = useRef({ sites, onSelect, fit })
  useEffect(() => {
    latest.current = { sites, onSelect, fit }
  })

  useEffect(() => {
    let cancelled = false
    // Held here as well as in `map`, so an unmount before 'load' (StrictMode's double
    // mount does exactly that) still removes the map it started.
    let built: MapLibreMap | null = null
    void Promise.all([
      import('maplibre-gl'),
      // MapLibre 6 looks for its worker beside its own module, which after bundling is the
      // app chunk, where no worker was ever emitted; the map then draws nothing and says
      // nothing. Vite emits it instead, the way client/src/map/mapWorker.ts does for OurHike.
      import('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'),
      import('maplibre-gl/dist/maplibre-gl.css'),
    ]).then(([maplibre, worker]) => {
      if (maplibre.getWorkerUrl() !== worker.default)
        maplibre.setWorkerUrl(worker.default)
      if (cancelled || !container.current) return
      const m = (built = new maplibre.Map({
        container: container.current,
        style: USE_FIXTURES ? PLAIN : BASEMAP,
        center: [-79, 38],
        zoom: 4,
        attributionControl: { compact: true },
      }))
      m.addControl(new maplibre.NavigationControl({ showCompass: false }), 'top-left')
      m.on('load', () => {
        m.addSource('sites', { type: 'geojson', data: asGeoJson(latest.current.sites) })
        m.addLayer({
          id: 'sites',
          type: 'circle',
          source: 'sites',
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 3, 12, 7],
            'circle-color': [
              'match',
              ['get', 'tier'],
              'P1',
              '#d9481f',
              'P2',
              '#c98a0b',
              'P3',
              '#5e7f6e',
              '#8a9799',
            ],
            'circle-stroke-color': ['case', ['get', 'official'], '#15252a', '#ffffff'],
            'circle-stroke-width': 1.5,
          },
        })
        m.on('click', 'sites', (event) => {
          const id = event.features?.[0]?.properties?.id
          const site = latest.current.sites.find((s) => s.rims_id === id)
          if (site) latest.current.onSelect?.(site)
        })
        m.on('mouseenter', 'sites', () => (m.getCanvas().style.cursor = 'pointer'))
        m.on('mouseleave', 'sites', () => (m.getCanvas().style.cursor = ''))
        if (cancelled) return
        map.current = m
        showSites(m, latest.current.sites, latest.current.fit)
      })
    })
    return () => {
      cancelled = true
      built?.remove()
      map.current = null
    }
    // The map is built once; the effect below keeps its sites current.
  }, [])

  useEffect(() => {
    if (map.current) showSites(map.current, sites, fit)
  }, [sites, fit])

  return (
    <div ref={container} className="map" aria-label="Map of the sites" role="region" />
  )
}

function showSites(m: MapLibreMap, sites: Site[], fit: boolean) {
  const source = m.getSource('sites')
  if (source && 'setData' in source)
    (source as { setData: (d: FeatureCollection) => void }).setData(asGeoJson(sites))
  if (!fit || sites.length === 0) return
  const lons = sites.map((s) => s.lon)
  const lats = sites.map((s) => s.lat)
  m.fitBounds(
    [
      [Math.min(...lons), Math.min(...lats)],
      [Math.max(...lons), Math.max(...lats)],
    ],
    { padding: 40, maxZoom: 15, duration: 0 },
  )
}
