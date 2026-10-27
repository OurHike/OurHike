// The moments usage measurement records, wired in one place (#1902,
// features/EVENTING.md §0).
//
// App.tsx renders lib/DeferredMeasureUsage.tsx, which loads this hook behind
// import() and runs it in a component that renders nothing - none of
// measurement is parsed before the first frame (features/LAUNCH_BUDGET.md §3:
// when this hook and the registry were eager they put the launch 1,947 bytes
// over a budget `main` clears by 287). App's plan handlers call back in through
// the handle that component fills; every other moment is noticed here, so the
// hot file carries one element and a handful of one-line calls rather than
// the logic (BRANCHING.md §2 on why App.tsx is the file to keep out of).
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
// remembers which account recorded it (lib/accountTag.ts), and is sent with a
// token only while the same account is signed in with its yes standing. The
// token goes with linked batches and with no others.

import { useCallback, useEffect, useMemo, useRef } from 'react'

import { accountTag } from './accountTag'
import type { Hike } from './hikes'
import type { HikePlan } from './plan'
import { takeFinishedSignIn } from './signInMarker'
import { traceShell } from './tracePlatform'
import { mileOnTrail, type TrailIndex } from './trailPosition'
import type { GeolocationState } from './useGeolocation'
import {
  type ClubRunLike,
  clubAtTrailMile,
  type HeldFix,
  milesByClub,
  SESSION_IDLE_MS,
  sessionLength,
  sharesFromMiles,
  stampHeartbeat,
  type UsageDetails,
  type UsageEventName,
  usableFix,
  usageRow,
} from './usageEvents'
import { hikeExtent, planExtent } from './usagePlans'
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
  /** "Link them to my account": null until the hiker has answered. */
  linked: boolean | null
  /** The signed-in account's email, or null. Never sent - see lib/accountTag.ts. */
  accountEmail: string | null
  /** First run is not finished - read once, when `ready` first turns true. */
  newInstall: boolean
  /**
   * The app's version (lib/buildInfo.ts), handed in rather than imported:
   * the shell already holds it, and importing it here split it out of the
   * first frame's chunk into one of its own (#1903's launch-budget fix).
   */
  version: string
  online: boolean
  /** Reports and other work in the outbox. Usage waits until this is zero. */
  reportsWaiting: number
  /** Anything that changes when the screen shown changes. Counted, never sent. */
  screen: string
  mapInView: boolean
  /** The map's own position answer; only a fix it already holds is sent. */
  gps: GeolocationState
  /** The map's camera, for the club a map view is about. */
  camera: { center: readonly [number, number] } | null
  /** The downloaded A.T.'s index, for the mile - and so the club - at a point. */
  trailIndex: TrailIndex | null
  /** The A.T.'s club runs, for the club at a mile and a plan's split by miles. */
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

/**
 * What App hands over for a plan: the plan or hike itself, whose extent is
 * worked out here (lib/usagePlans.ts) rather than in the first frame's chunk,
 * or an extent App already has.
 */
export type PlanSource = PlanExtent | { plan: HikePlan } | { hike: Hike }

export interface UsageMeasurement {
  planMade: (source: PlanSource) => void
  planCompleted: (source: PlanSource) => void
}

function extentOf(source: PlanSource): PlanExtent {
  if ('plan' in source) return planExtent(source.plan)
  if ('hike' in source) return hikeExtent(source.hike)
  return source
}

function planDetails(source: PlanSource, clubRuns: readonly ClubRunLike[]): UsageDetails {
  const extent = extentOf(source)
  const { fromMile, toMile } = extent
  if (
    fromMile !== undefined &&
    toMile !== undefined &&
    Number.isFinite(fromMile) &&
    Number.isFinite(toMile)
  ) {
    return {
      miles: extent.miles ?? Math.abs(toMile - fromMile),
      clubs: sharesFromMiles(milesByClub(clubRuns, fromMile, toMile)),
    }
  }
  return extent.miles === undefined ? {} : { miles: extent.miles }
}

/** The fix the map holds, as measurement reads it. */
function heldFix(gps: GeolocationState): HeldFix | null {
  return gps.status === 'located'
    ? { lat: gps.at.lat, lon: gps.at.lon, accuracy: gps.accuracyM, at: gps.fixedAt }
    : null
}

/** The tag of the account a row may be linked to now, or null. */
function linkedAccount(input: UsageMeasurementInput): string | null {
  return input.linked === true && input.accountEmail !== null
    ? accountTag(input.accountEmail)
    : null
}

export function useUsageMeasurement(input: UsageMeasurementInput): UsageMeasurement {
  // Read through a ref by every callback below, so a handler App created once
  // still records with the hiker's current answers and the newest fix.
  // Updated in the first effect, so every effect after it reads this render's.
  const latest = useRef(input)
  useEffect(() => {
    latest.current = input
  })

  const pointClubs = useCallback(
    (lon: number, lat: number): Record<string, number> | undefined => {
      const { trailIndex, clubRuns } = latest.current
      const mile = trailIndex === null ? null : mileOnTrail(trailIndex, { lon, lat })
      const club = mile === null ? null : clubAtTrailMile(clubRuns, mile)
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
      const fix = withFix ? usableFix(heldFix(current.gps), at) : undefined
      const clubs =
        details.clubs ?? (fix === undefined ? undefined : pointClubs(fix.lon, fix.lat))
      const linkedTo = linkedAccount(current)
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
          version: current.version,
          stamp,
          signedIn: current.accountEmail !== null,
          details: {
            ...details,
            ...(clubs === undefined ? {} : { clubs }),
            ...(fix === undefined ? {} : { fix }),
          },
        })
        return withRows({ ...store, heartbeat: next }, [{ row, linkedTo }])
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
          // SENT ON THE WAY OUT, not only every five minutes: a phone that
          // opens the app once for two minutes and uninstalls it otherwise
          // never sends its install, and the hikers who try the app and leave
          // are exactly the ones a count must not lose. A send cut short by
          // the app closing loses nothing - a row leaves the queue only once
          // the server has answered for it.
          const { online, reportsWaiting } = latest.current
          if (online && reportsWaiting === 0)
            void flushUsage(undefined, linkedAccount(latest.current))
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
    const { camera } = latest.current
    const centre = camera === null ? null : camera.center
    void record('map_screen_viewed', {
      clubs: centre === null ? undefined : pointClubs(centre[0], centre[1]),
    })
  }, [input.mapInView, record, pointClubs])

  // --- sign-in -------------------------------------------------------------------------
  // The marker is taken whether or not counting is on: a sign-in finishes
  // once, and a marker left lying would count the next restored session.
  const signedIn = input.accountEmail !== null
  useEffect(() => {
    if (!signedIn || !input.ready) return
    if (!takeFinishedSignIn()) return
    if (!latest.current.enabled) return
    void record('user_login', {})
    latest.current.onSignIn?.()
  }, [signedIn, input.ready, record])

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
  const linkedNow = linkedAccount(input)
  const wasLinked = useRef(linkedNow)
  useEffect(() => {
    if (wasLinked.current !== null && linkedNow === null && signedIn && input.ready)
      void unlinkWaitingRows()
    wasLinked.current = linkedNow
  }, [linkedNow, signedIn, input.ready])

  // --- sending, after the hiker's own work ----------------------------------------------
  const canSend =
    input.ready && input.enabled && input.online && input.reportsWaiting === 0
  useEffect(() => {
    if (!canSend) return
    // The account that matters is the one signed in when the batch leaves.
    void flushUsage(undefined, linkedAccount(latest.current))
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible')
        void flushUsage(undefined, linkedAccount(latest.current))
    }, FLUSH_EVERY_MS)
    return () => window.clearInterval(timer)
  }, [canSend])

  return useMemo(
    () => ({
      planMade: (source: PlanSource) =>
        void record('hike_plan_made', planDetails(source, latest.current.clubRuns)),
      planCompleted: (source: PlanSource) =>
        void record('hike_plan_completed', planDetails(source, latest.current.clubRuns)),
    }),
    [record],
  )
}
