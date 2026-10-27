import { useEffect, useState } from 'react'

export type Route =
  | { screen: 'sites' }
  | { screen: 'site'; id: string }
  | { screen: 'analysis' }
  | { screen: 'guide' }

/** Hash routes, so the app is a folder of static files that any host can serve. */
export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#\/?/, '')
  const [first, second] = path.split('/')
  if (first === 'site' && second)
    return { screen: 'site', id: decodeURIComponent(second) }
  if (first === 'analysis') return { screen: 'analysis' }
  if (first === 'guide') return { screen: 'guide' }
  return { screen: 'sites' }
}

export function siteHref(id: string): string {
  return `#/site/${encodeURIComponent(id)}`
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash))
  useEffect(() => {
    const onChange = () => {
      setRoute(parseRoute(window.location.hash))
      window.scrollTo?.(0, 0)
    }
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}
