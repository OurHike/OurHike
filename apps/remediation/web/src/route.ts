import { useEffect, useState } from 'react'

export type Route =
  | { screen: 'sites' }
  | { screen: 'site'; id: string }
  | { screen: 'analysis' }
  | { screen: 'guide' }
  | { screen: 'account' }
  | { screen: 'lists' }
  | { screen: 'shared'; token: string }
  | { screen: 'claim'; id: string }
  | { screen: 'join'; token: string }
  | { screen: 'work' }

/** Hash routes, so the app is a folder of static files that any host can serve. */
export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#\/?/, '')
  const [first, second] = path.split('/')
  if (first === 'site' && second)
    return { screen: 'site', id: decodeURIComponent(second) }
  if (first === 'analysis') return { screen: 'analysis' }
  if (first === 'guide') return { screen: 'guide' }
  if (first === 'account') return { screen: 'account' }
  if (first === 'lists') return { screen: 'lists' }
  if (first === 'shared' && second)
    return { screen: 'shared', token: decodeURIComponent(second) }
  if (first === 'claim' && second)
    return { screen: 'claim', id: decodeURIComponent(second) }
  if (first === 'join' && second)
    return { screen: 'join', token: decodeURIComponent(second) }
  if (first === 'work') return { screen: 'work' }
  return { screen: 'sites' }
}

export function siteHref(id: string): string {
  return `#/site/${encodeURIComponent(id)}`
}

export function claimHref(id: string): string {
  return `#/claim/${encodeURIComponent(id)}`
}

/** A crew invite, like a share link, rides in the hash and so never reaches the static host. */
export function joinHref(token: string): string {
  return `#/join/${encodeURIComponent(token)}`
}

/** A share token rides in the hash, so the static host never sees it in a request. */
export function sharedHref(token: string): string {
  return `#/shared/${encodeURIComponent(token)}`
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
