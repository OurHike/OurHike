// The moments usage measurement records, wired in one place (#1902,
// features/EVENTING.md §0).
//
// App.tsx calls this once and calls back into it from the handlers that make
// and finish plans; every other moment is noticed here, so the hot file
// carries one hook and a handful of one-line calls rather than the logic
// (BRANCHING.md §2 on why App.tsx is the file to keep out of).
//
//   app_installed        the first launch of an install that had not finished
//                        first run - an install that predates measurement is
//                        not counted as new, and neither is its first event
//   user_login           a sign-in this app started, finishing (lib/signInMarker.ts)
//   hike_plan_made /     the handlers in App, through `planMade` / `planCompleted`
//   hike_plan_completed
//   map_screen_viewed    the map coming into view, once per arrival
//   session              a visit, sent when it is over: hidden for longer than
//                        `SESSION_IDLE_MS`, or found unfinished at the next
//                        launch because the phone killed the app
//
// NOTHING IS RECORDED WHILE "Share usage statistics" IS OFF, and turning it
// off empties the queue - lib/usageQueue.ts `clearUsage`. A row is LINKED to
// the account only while the hiker's answer to "Link your usage to your
// account?" is yes AND they are signed in, and only to THAT account: each row
// remembers which account recorded it (`accountTag`), and is sent with a
// token only while the same account is signed in with its yes standing. The
// token goes with linked batches and with no others.

import { useCallback, useEffect, useMemo, useRef } from 'react'

import { BUILD_INFO } from './buildInfo'
import { takeFinishedSignIn } from './signInMarker'
import { traceShell } from './tracePlatform'
import {
  type ClubRunLike,
  type HeldFix,
  type UsageDetails,
  type UsageEventName,
  milesByClub,
  SESSION_IDLE_MS,
  sessionLength,
  sharesFromMiles,
  stampHeartbeat,
  usableFix,
  usageRow,
} from './usageEvents'
import {
  clearUsage,
  flushUsage,
  type PendingSession,
  readUsage,
  unlinkWaitingRows,
  updateUsage,
  type UsageStore,
  withRows,
} from './usageQueue'

/** How often a visible app tries to send, besides the moments below. */
export const FLUSH_EVERY_MS = 5 * 60 * 1000

export interface UsageMeasurementInput {
  /** Preferences have loaded, so `enabled` and `linked` are the hiker's own. */
  ready: boolean
  /** "Share usage statistics". */
  enabled: boolean
  /**
   * `accountTag` of the signed-in account while its "Link them to my
   * account" is yes, otherwise null.
   */
  linkedAccount: string | null
  /** First run is not finished - read once, when `ready` first turns true. */
  newInstall: boolean
  signedIn: boolean
  online: boolean
  /** Reports and other work in the outbox. Usage waits until this is zero. */
  reportsWaiting: number
  /** Anything that changes when the screen shown changes. Counted, never sent. */
  screen: string
  mapInView: boolean
  heldFix: HeldFix | null
  /** The map's centre as `[lon, lat]`, for the club a map view is about. */
  mapCentre: readonly [number, number] | null
  /** The club at a point on the trail, or null off it. */
  clubAtPoint: (lon: number, lat: number) => string | null
  /** The A.T.'s club runs, for splitting a plan by its miles. */
  clubRuns: readonly ClubRunLike[]
  /** A sign-in this app started has finished, while sharing is on. */
  onSignIn?: () => void
}

/** A plan, as far as measurement needs it: its A.T. miles, or just its length. */
export interface PlanExtent {
  fromMile?: number
  toMile?: number
  miles?: number
}

export interface UsageMeasurement {
  planMade: (extent: PlanExtent) => void
  planCompleted: (extent: PlanExtent) => void
}

function planDetails(extent: PlanExtent, clubRuns: readonly ClubRunLike[]): UsageDetails {
  const { fromMile, toMile } = extent
  if (
    fromMile !== undefined &&
    toMile !== undefined &&
    Number.isFinite(fromMile) &&
    Number.isFinite(toMile)
  ) {
    const byClub = milesByClub(clubRuns, fromMile, toMile)
    return {
      miles: extent.miles ?? Math.abs(toMile - fromMile),
      clubs: sharesFromMiles(byClub),
    }
  }
  return extent.miles === undefined ? {} : { miles: extent.miles }
}

export function useUsageMeasurement(input: UsageMeasurementInput): UsageMeasurement {
  // Read through a ref by every callback below, so a handler App created once
  // still records with the hiker's current answers and the newest fix.
  const latest = useRef(input)
  latest.current = input

  const pointClubs = useCallback(
    (lon: number, lat: number): Record<string, number> | undefined => {
      const club = latest.current.clubAtPoint(lon, lat)
      return club === null ? undefined : { [club]: 1 }
    },
    [],
  )

  /** Stamp and queue one row. `at` is the moment it describes. */
  const record = useCallback(
    async (
      event: UsageEventName,
      details: UsageDetails,
      at: Date = new Date(),
      withFix = true,
    ) => {
      const current = latest.current
      if (!current.ready || !current.enabled) return
      const fix = withFix ? usableFix(current.heldFix, at) : undefined
      const clubs =
        details.clubs ?? (fix === undefined ? undefined : pointClubs(fix.lon, fix.lat))
      await updateUsage((store) => {
        const { stamp, next } = stampHeartbeat(
          store.heartbeat,
          at,
          Object.keys(clubs ?? {}),
          event,
        )
        const row = usageRow({
          id: crypto.randomUUID(),
          event,
          now: at,
          platform: traceShell(),
          version: BUILD_INFO.version,
          stamp,
          signedIn: current.signedIn,
          details: {
            ...details,
            ...(clubs === undefined ? {} : { clubs }),
            ...(fix === undefined ? {} : { fix }),
          },
        })
        return withRows({ ...store, heartbeat: next }, [
          { row, linkedTo: current.linkedAccount },
        ])
      })
    },
    [pointClubs],
  )

  /** The row for a visit that is over, dated the day it started. */
  const endSession = useCallback(
    async (session: PendingSession) => {
      await record(
        'session',
        {
          pageviews: session.pageviews,
          session_length: sessionLength(
            Math.max(0, session.lastSeenAt - session.startedAt),
          ),
        },
        new Date(session.startedAt),
        // The fix must describe the visit: one taken after it ended does not.
        Date.now() - session.lastSeenAt <= SESSION_IDLE_MS,
      )
    },
    [record],
  )

  // --- first launch, and the visit in progress -----------------------------------
  const started = useRef(false)
  useEffect(() => {
    if (!input.ready || !input.enabled || started.current) return
    started.current = true
    void (async () => {
      const store: UsageStore = await readUsage()
      if (!store.initialized) {
        if (latest.current.newInstall)
          await record('app_installed', {}, new Date(), false)
        // An install that finished first run before measurement existed is not
        // a new device either: its first event must not say `ever_first`.
        await updateUsage((current) => ({
          ...current,
          initialized: true,
          heartbeat: latest.current.newInstall
            ? current.heartbeat
            : { ...current.heartbeat, ever: true },
        }))
      }
      if (store.session !== null) await endSession(store.session)
      const now = Date.now()
      await updateUsage((current) => ({
        ...current,
        session: { startedAt: now, lastSeenAt: now, pageviews: 1 },
      }))
    })()
  }, [input.ready, input.enabled, record, endSession])

  useEffect(() => {
    const onVisibility = () => {
      if (!latest.current.ready || !latest.current.enabled) return
      const now = Date.now()
      void (async () => {
        if (document.visibilityState === 'hidden') {
          await updateUsage((store) =>
            store.session === null
              ? store
              : { ...store, session: { ...store.session, lastSeenAt: now } },
          )
          return
        }
        const { session } = await readUsage()
        if (session !== null && now - session.lastSeenAt <= SESSION_IDLE_MS) {
          await updateUsage((store) =>
            store.session === null
              ? store
              : { ...store, session: { ...store.session, lastSeenAt: now } },
          )
          return
        }
        if (session !== null) await endSession(session)
        await updateUsage((store) => ({
          ...store,
          session: { startedAt: now, lastSeenAt: now, pageviews: 1 },
        }))
      })()
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [endSession])

  // --- pageviews ---------------------------------------------------------------------
  const lastScreen = useRef<string | null>(null)
  useEffect(() => {
    const previous = lastScreen.current
    lastScreen.current = input.screen
    if (previous === null || previous === input.screen || !input.ready || !input.enabled)
      return
    const now = Date.now()
    void updateUsage((store) =>
      store.session === null
        ? store
        : {
            ...store,
            session: {
              ...store.session,
              pageviews: store.session.pageviews + 1,
              lastSeenAt: now,
            },
          },
    )
  }, [input.screen, input.ready, input.enabled])

  // --- the map coming into view --------------------------------------------------------
  const mapWasInView = useRef(false)
  useEffect(() => {
    const arrived = input.mapInView && !mapWasInView.current
    mapWasInView.current = input.mapInView
    if (!arrived) return
    const centre = latest.current.mapCentre
    void record('map_screen_viewed', {
      clubs: centre === null ? undefined : pointClubs(centre[0], centre[1]),
    })
  }, [input.mapInView, record, pointClubs])

  // --- sign-in -------------------------------------------------------------------------
  useEffect(() => {
    if (!input.signedIn || !input.ready) return
    if (!takeFinishedSignIn()) return
    if (!latest.current.enabled) return
    void record('user_login', {})
    latest.current.onSignIn?.()
  }, [input.signedIn, input.ready, record])

  // --- the two switches ------------------------------------------------------------------
  useEffect(() => {
    if (input.ready && !input.enabled) {
      started.current = false
      void clearUsage()
    }
  }, [input.ready, input.enabled])

  // A no said while signed in unlinks what is still waiting. A sign-out needs
  // nothing here: rows recorded under the account that left no longer match
  // whoever is signed in, so they go without an account by themselves.
  const wasLinked = useRef(input.linkedAccount)
  useEffect(() => {
    if (
      wasLinked.current !== null &&
      input.linkedAccount === null &&
      input.signedIn &&
      input.ready
    )
      void unlinkWaitingRows()
    wasLinked.current = input.linkedAccount
  }, [input.linkedAccount, input.signedIn, input.ready])

  // --- sending, after the hiker's own work ----------------------------------------------
  const canSend =
    input.ready && input.enabled && input.online && input.reportsWaiting === 0
  useEffect(() => {
    if (!canSend) return
    void flushUsage(undefined, latest.current.linkedAccount)
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible')
        void flushUsage(undefined, latest.current.linkedAccount)
    }, FLUSH_EVERY_MS)
    return () => window.clearInterval(timer)
  }, [canSend])

  return useMemo(
    () => ({
      planMade: (extent: PlanExtent) =>
        void record('hike_plan_made', planDetails(extent, latest.current.clubRuns)),
      planCompleted: (extent: PlanExtent) =>
        void record('hike_plan_completed', planDetails(extent, latest.current.clubRuns)),
    }),
    [record],
  )
}
