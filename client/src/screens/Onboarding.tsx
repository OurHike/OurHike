// First run (WIREFRAMES.md §5, reshaped by #1054). Three steps, each skippable.
//
// A card over the live map, not a page instead of it. The shell puts the map
// behind these steps (App.tsx's onboarding branch) and this file is the half
// of that which leaves room to see it: the card is anchored to the bottom of
// the screen, capped well short of filling it, and scrolls its own contents if
// they outgrow that - so the map is visible above the steps on every screen
// size rather than only on tall ones. The brand lockup at the top rides a
// gradient that fades to nothing, never a scrim: dimming the map to introduce
// the map is still a strange way to introduce it. (#1054's design drew a
// full-bleed photograph here instead; that lands with the photograph itself,
// as its own recorded reversal of this file's rule, not as a side effect.)
//
// What is NOT here matters as much as what is:
//
//  - No notification prompt. OurHike sends no push notifications, so there
//    is nothing here to ask permission for.
//  - No account prompt. Reading the map never needs an account; sign-in is
//    asked at the first contribution instead.
//
// The step counter comes from lib/onboardingSteps.ts, so a skipped step still
// counts and the total cannot grow mid-flow.
//
// THE DOWNLOAD STARTS ON THE STEP THAT ASKS FOR IT (#1054).
//
// This file used to argue the opposite - "no progress, no buttons, nothing on
// the phone to delete... duplicating it would mean starting a download inside
// a flow whose last step has not been asked yet" - and first run ended by
// opening the download window over the map. That was two consecutive views of
// one decision (#298 closed most of the gap by making them the same shape),
// and the newcomer still had to re-answer it. The redesign takes the last
// step: "Keep going" on the size step starts the transfer through the shell's
// own machinery (lib/archiveDownload.ts's resume semantics included), the
// location step is asked while the bytes arrive, and the panel below says so
// honestly. The old worry - a download racing a flow that is not finished -
// is answered by what #553 built since: the transfer is the shell's, survives
// this component unmounting, checkpoints to disk as it arrives, and "Decide
// this later" still starts nothing. The download window is the MANAGE surface
// now; App.tsx no longer opens it at completion.
//
// #277 still holds: the USGS tab, when a second sheet is on offer, is named
// and priced here and never configured - see SHEET_TABS.

import { useState } from 'react'
import logoIcon from '../design-system/assets/logo-icon.svg'
import { pickHero } from '../lib/heroPhotos'
import { ONBOARDING_STEPS, buildOnboardingProgress } from '../lib/onboardingSteps'
import type { HikingDetailLevel } from '../lib/userPreferences'
import { HIKING_SHEET, offeredSheets, USGS_SHEET } from '../lib/packages'
import { DetailPicker, hikingDetailOptions, rasterDetailOptions } from './DetailPicker'
import { usePublishedSizes } from '../lib/usePublishedSizes'
import { useAvailableBytes } from '../lib/useAvailableBytes'
import {
  downloadFillPercent,
  downloadPercent,
  type DownloadActivity,
} from '../lib/downloadActivity'
import { formatBytes, formatBytesLive } from '../lib/formatBytes'
import { Tabs } from './Tabs'
import { PlaceField } from '../chrome/PlaceField'
import { snapshotPlace, type DefaultPlace } from '../lib/defaultPlace'
import { NO_PLACES, type Place, type PlacesDocument } from '../lib/places'
import type { UnitSystem } from '../lib/units'
import { HIKER_MODE_LABELS, HIKER_MODE_VALUES, type HikerMode } from '../lib/hikerMode'
import { ModeIcon } from '../chrome/ModeIcon'
import './onboarding.css'

/**
 * How much of the viewport the entry card is allowed to cover.
 *
 * The twin of `max-height` in onboarding.css, and the reason it is a number
 * here rather than only a CSS declaration: the map behind these steps has to be
 * framed against the part of the screen the card does NOT cover, which is
 * something only the map can do and only if it knows this figure
 * (App.tsx's `entryFitPadding`). test/entryLayout.test.ts asserts the two agree,
 * because a stylesheet and a constant drifting apart would leave the trail
 * fitted to a screen nobody can see.
 */
export const ENTRY_CARD_MAX_VIEWPORT_FRACTION = 0.78

export interface OnboardingResult {
  /** The hiking sheet's level (#276/#277) - the download decision this flow
   *  actually shows, so the preference written matches the choice made. */
  hikingDetailLevel: HikingDetailLevel
  locationRequested: boolean
  /** Where the hiker said they hike (#1373, frame 1b), or null when the
   *  step was skipped. A snapshot for lib/defaultPlace.ts, never an id. */
  defaultPlace: DefaultPlace | null
  /**
   * What brings them out - Day hike, Long hike or Volunteer - or null when
   * the card was skipped, which the card says aloud means Day hike (the
   * shell's DEFAULT_HIKER_MODE). Null rather than 'day' so the shell can
   * tell a choice from a default and write only the choice.
   */
  hikerMode: HikerMode | null
}

/**
 * One line under each mode, in Today's own voice (screens/Today.tsx's setup
 * heads say the same things at more length). Copy, not data: the labels are
 * lib/hikerMode.ts's and only the sentence is this card's.
 */
const MODE_NOTES: Record<HikerMode, string> = {
  day: 'Out and back by dark. Walks near you, and a builder for one of your own.',
  long: 'One trail, broken into days. Sections, water and camp to camp.',
  volunteer: 'Workdays and the crew, with the trail in the background.',
}

export interface OnboardingProps {
  onComplete: (result: OnboardingResult) => void
  /**
   * The level choice, written through as it changes (#1054) - the shell's
   * download requests derive their URLs from the stored preference, so the
   * write has to land before "Keep going" starts the transfer, not at the
   * end of the flow. Omitted, the choice still lands via onComplete.
   */
  onChangeLevel?: (level: HikingDetailLevel) => void
  /**
   * Start the hiking sheet's download, from the size step itself (#1054).
   * The transfer is the shell's - it outlives these steps, checkpoints as it
   * arrives (lib/archiveDownload.ts), and resumes if the signal goes.
   * Omitted, the button still advances and nothing is fetched.
   */
  onStartDownload?: () => void
  /** What is moving right now (lib/downloadActivity.ts), for the inline
   *  panel - null while nothing is. */
  downloadActivity?: DownloadActivity | null
  /**
   * The places the "where do you hike?" step resolves against (#1373,
   * lib/usePlaces.ts), and whether every read of them has answered. Omitted,
   * the step says there is nothing on the phone to search and offers the
   * way past - the field never blocks the flow.
   */
  places?: PlacesDocument
  placesSettled?: boolean
  online?: boolean
  /** For the miles of trail a place row prints. Imperial until the hiker
   *  has said otherwise, which on first run they have not. */
  units?: UnitSystem
}

/**
 * The sheets on offer, in the download window's own order - the background
 * everyone gets first, any optional second map after it. Named from the
 * catalog so first run and the window cannot come to call them different
 * things, and FILTERED by it too: a withdrawn sheet is not something to put
 * in front of a newcomer, and since #855 that is the USGS raster.
 *
 * So this is usually one tab today, and the strip disappears when it is -
 * the download window's own rule, for its own reason (Downloads.tsx): "a
 * single tab is a heading pretending to be a control". The two screens are
 * two consecutive views of one decision and they have to keep looking like
 * it.
 */
const SHEET_TABS = offeredSheets().map((sheet) => ({ id: sheet.id, label: sheet.title }))

/** The inline progress panel: the transfer the size step started, stated
 *  honestly in each of its three states (lib/downloadActivity.ts). */
function DownloadPanel({ activity }: { activity: DownloadActivity }) {
  if (activity.kind === 'preparing') {
    return (
      <div className="onboarding__download" role="status">
        <p className="onboarding__download-label">
          Getting the trail&rsquo;s own data first &mdash; the map follows.
        </p>
      </div>
    )
  }

  const percent = downloadPercent(activity.doneBytes, activity.totalBytes)
  return (
    <div className="onboarding__download" role="status">
      <div className="onboarding__download-head">
        <p className="onboarding__download-label">
          {activity.kind === 'checking'
            ? 'Checking what is already on this phone'
            : 'Downloading while you finish up'}
        </p>
        <span className="onboarding__download-percent">{percent}%</span>
      </div>
      <div className="onboarding__download-bar" aria-hidden="true">
        <div
          className="onboarding__download-fill"
          style={{
            width: `${downloadFillPercent(activity.doneBytes, activity.totalBytes)}%`,
          }}
        />
      </div>
      {/* The resume promise is lib/archiveDownload.ts's, surfaced where the
          worry actually is: someone watching a bar on trailhead wifi.

          formatBytesLive for the moving figure, not formatBytes - this
          shipped with the static formatter and the maintainer watched the
          decimal spin: "don't show decimals. That makes the text all jumpy
          and crazy" (2026-08-26), which is the exact flicker
          lib/formatBytes.ts built the live variant to stop. The reserved
          slot is DownloadCard.tsx's trick, sized to the total (the widest
          the counter gets, exact in ch because the face is mono) so "of
          1.4 GB" never shuffles sideways as 99 MB becomes 100 MB. */}
      <p className="onboarding__download-meta">
        <span
          className="onboarding__download-received"
          style={{ minWidth: `${formatBytesLive(activity.totalBytes).length}ch` }}
        >
          {formatBytesLive(activity.doneBytes)}
        </span>
        {` of ${formatBytes(activity.totalBytes)} · picks up where it left off if you lose signal`}
      </p>
    </div>
  )
}

export function Onboarding({
  onComplete,
  onChangeLevel,
  onStartDownload,
  downloadActivity = null,
  places = NO_PLACES,
  placesSettled = true,
  online = false,
  units = 'imperial',
}: OnboardingProps) {
  const [stepIndex, setStepIndex] = useState(0)
  // The mode taken on the "what brings you out?" card, or null until one is
  // - and null on through the skip, which is the shell's cue to keep its
  // default rather than write a choice nobody made.
  const [mode, setMode] = useState<HikerMode | null>(null)
  // The row taken on the "where do you hike?" step, held as the live index
  // row until the flow finishes and snapshots it (lib/defaultPlace.ts).
  const [place, setPlace] = useState<Place | null>(null)
  // Standard is pre-selected, so skipping every step still leaves a usable
  // map to download rather than no choice at all.
  const [hikingLevel, setHikingLevel] = useState<HikingDetailLevel>('standard')
  // Opens on the sheet this step is actually sizing (#277).
  const [openSheetId, setOpenSheetId] = useState(HIKING_SHEET.id)
  // Once, however the steps are walked: "Keep going" tapped twice, or a
  // hiker backing through browser history, must not start a second transfer
  // (useArchiveDownloads dedups too - this is the cheap first line).
  const [downloadStarted, setDownloadStarted] = useState(false)

  // Drawn once per first run, held in state so the backdrop does not
  // reshuffle as the steps advance - the card remounts per step (keyed
  // below); this component does not. lib/heroPhotos.ts is the pool and the
  // reasoning; the credit rendered on the frame belongs to this draw.
  const [hero] = useState(() => pickHero())
  // So a level this phone cannot hold is greyed before it is chosen, rather
  // than refused after the newcomer has committed to it (#555).
  const { bytes: availableBytes } = useAvailableBytes()
  // The sizes this step prints come from what the bucket published, not from a
  // constant kept by hand (#505). Empty until latest.json lands - and on first
  // run it usually lands after the card paints - so the ladder shows its
  // fallback figures and then re-renders with the measured ones.
  const publishedSizes = usePublishedSizes()

  const step = ONBOARDING_STEPS[stepIndex]
  const progress = buildOnboardingProgress({
    currentStepId: step.id,
    skippedStepIds: [],
  })

  /** The open sheet's body - its summary and its levels. Lifted out of the
   *  tab strip because it is now rendered with or without one, and a panel
   *  that only exists inside `<Tabs>` cannot be shown when there is nothing
   *  to switch between. */
  const sheetPanel =
    openSheetId === HIKING_SHEET.id ? (
      <>
        <p className="onboarding__sheet-summary">{HIKING_SHEET.summary}</p>
        <DetailPicker
          options={hikingDetailOptions(publishedSizes)}
          value={hikingLevel}
          onChange={(level) => {
            setHikingLevel(level as HikingDetailLevel)
            onChangeLevel?.(level as HikingDetailLevel)
          }}
          name="onboarding-detail"
          availableBytes={availableBytes}
        />
      </>
    ) : (
      <>
        <p className="onboarding__sheet-summary">{USGS_SHEET.summary}</p>
        {/* Named and priced, not configured (#277). Locked rather
            than absent so the newcomer can see what the optional map
            would cost before deciding they want it at all. */}
        <DetailPicker
          options={rasterDetailOptions(publishedSizes)}
          value=""
          onChange={() => undefined}
          name="onboarding-usgs-detail"
          locked
          lockedNote="Chosen in Downloads, any time. This step is sizing the map you navigate by."
          availableBytes={availableBytes}
        />
      </>
    )

  const finish = (locationRequested: boolean) =>
    onComplete({
      hikingDetailLevel: hikingLevel,
      locationRequested,
      defaultPlace: place === null ? null : snapshotPlace(place),
      hikerMode: mode,
    })

  /** What the size step's primary says it will do, with the chosen rung's
   *  own figure - "Download 458.4 MB" - or just the verb while the manifest
   *  has not said what the rung weighs. */
  const chosenRung = hikingDetailOptions(publishedSizes).find((o) => o.id === hikingLevel)
  const downloadLabel =
    chosenRung?.sizeBytes == null
      ? 'Download'
      : `Download ${formatBytes(chosenRung.sizeBytes)}`

  const next = () => {
    if (stepIndex < ONBOARDING_STEPS.length - 1) setStepIndex(stepIndex + 1)
    else finish(false)
  }

  const startDownloadAndGo = () => {
    if (onStartDownload !== undefined && !downloadStarted) {
      setDownloadStarted(true)
      onStartDownload()
    }
    next()
  }

  return (
    <main className="onboarding">
      {/* The trail itself, behind the steps (#1054). This REVERSES the
          #721-era rule that the map stays visible behind first run - the
          reasoning is in onboarding.css's header, and test/entryLayout.test.ts
          records what the contract became. The map screen still renders inert
          underneath (that machinery is unchanged, and is why the map is warm
          the moment the steps finish); this overlay simply stands in front of
          it - the photo as a top band, pine ground below (see the CSS for
          why a band).

          WHICH photo changed the same day it shipped: one fixed pick went to
          the maintainer, came back "too bright green and too busy", and the
          answer was the whole gallery - lib/heroPhotos.ts is the pool, the
          licence bookkeeping, and the reasoning; the credit pill below
          belongs to whichever photo this run drew. Decorative to a screen
          reader either way: the steps are the content, the photo is the room
          they are read in. */}
      <div className="onboarding__hero" aria-hidden="true">
        <img className="onboarding__hero-image" src={hero.src} alt="" />
      </div>

      {/* The lockup, on a solid plate rather than loose over the photo. It
          began as ink on a fading gradient and the maintainer could not read
          it ("the grey is too light... add a grey background to that area
          and make the text white", 2026-08-26) - a fixed treatment cannot
          chase seventeen possible backdrops, so the plate is opaque enough
          to not care what loads behind it, the same trick the map's own
          identity plate pulls over arbitrary terrain (chrome.css .map-plate).

          The icon asset plus this file's own wordmark span, not <Logo />:
          the component inks its wordmark var(--stone-900) inline, which is
          unoverridable from a stylesheet and unreadable on a dark plate -
          the same reason chrome/TabBar.tsx composes the mark itself, and
          the same cost, recorded there: this is no longer the design
          system's fixed-ratio lockup. */}
      <div className="onboarding__brand" aria-hidden="true">
        <span className="onboarding__brand-lockup">
          <img className="onboarding__brand-icon" src={logoIcon} alt="" />
          <span className="onboarding__brand-wordmark">OurHike</span>
        </span>
        <p className="onboarding__tagline">
          Hike your own hike, and keep the trail in good hands.
        </p>
        {/* The photo's credit, at the plate's foot rather than loose on the
            frame: a floating pill collided with the plate on a 390px phone
            once the credits got as long as some of them are, and on the
            plate it is legible over all seventeen possible backdrops. The
            "Photo:" prefix keeps a photographer's name from reading as the
            app's. */}
        <p className="onboarding__hero-credit">Photo: {hero.credit}</p>
      </div>

      {/* Keyed by step, so React rebuilds this subtree when the step changes
          and the card's entry animation runs again for each one (onboarding.css
          reduces it to nothing under prefers-reduced-motion). The steps rise
          over the map one at a time rather than the copy inside a static panel
          being swapped out underneath the reader. */}
      <div key={step.id} className="onboarding__card">
        {/* Three bars and a mono fraction rather than prose; the sentence
            stays for a screen reader, which a row of coloured divs tells
            nothing. */}
        <div className="onboarding__progress">
          <span className="visually-hidden">{`Step ${progress.label}`}</span>
          <span className="onboarding__progress-bars" aria-hidden="true">
            {ONBOARDING_STEPS.map((s, index) => (
              <span
                key={s.id}
                className={
                  index <= stepIndex
                    ? 'onboarding__progress-bar onboarding__progress-bar--done'
                    : 'onboarding__progress-bar'
                }
              />
            ))}
          </span>
          <span className="onboarding__progress-count" aria-hidden="true">
            {progress.position} / {progress.total}
          </span>
        </div>

        {step.id === 'what-ourhike-is' && (
          <section className="onboarding__step">
            <h1 className="onboarding__title">
              A map that works where there is no signal.
            </h1>
            <p>
              Trails, water, shelters and resupply from the organizations that maintain
              them &mdash; downloaded to this phone.
            </p>
            {/*
              The money sentence, and the one thing on this screen that has to
              be exactly right.

              It read "Paid memberships and public support fund the ATC and the
              other organizations who keep these trails open" until 2026-08-27.
              Read in isolation that is true about how trail organizations are
              funded - dues plus public money - but no hiker reads it in
              isolation. Every other sentence on this screen has OurHike as its
              subject, and the line directly below says "No account. Nothing to
              sign up for." So "paid memberships" reads as OurHike's, and a
              hiker walks away believing their money would reach the ATC through
              this app. It would not, and there is no arrangement under which it
              would: **OurHike sends no money to any organization and has no
              revenue-sharing agreement with one.** The maintainer, 2026-08-27:
              "There is no funding model today for the orgs. The hope is we will
              drive membership and donations to those orgs."

              Neither half of the replacement is newly invented, deliberately.
              "your money belongs with the people holding the tools" is already
              live on ourhike.org/support, and "OurHike takes no cut and holds
              no money" is the sentence chrome/SourcesSection.tsx has been
              holding back for want of a donate link to attach it to (#932 -
              *sources.json can describe a steward but cannot say how to
              support one*).
              One posture in two voices - the web attributes it as opinion
              ("we just think your money belongs..."), and here it is asserted,
              because a first-run screen has no room to hedge and the thing
              being asserted is ours to assert: it is a statement about where
              OurHike's own hand is, not a claim about anybody else.
            */}
            <p>
              Your money belongs with the people holding the tools. The ATC, and other
              organizations who keep these trails open, take members and donations
              directly &mdash; OurHike takes no cut and holds no money.
            </p>
            <p className="onboarding__reassurance">No account. Nothing to sign up for.</p>
          </section>
        )}

        {/* What brings them out (the maintainer's review of #1374, 2026-09-10):
            the mode was being assigned silently, and it decides what Today
            shows and what step 1 builds. Three radios, none preselected - a
            default drawn as a choice would be the silent assignment in
            better clothes - and the primary is absent until one is taken
            (D10: no dead control). The skip says what skipping means. */}
        {step.id === 'hiker-mode' && (
          <section className="onboarding__step">
            <h1 className="onboarding__title">What brings you out?</h1>
            <p>
              Today changes with the answer &mdash; what leads, what is nearby, what a
              plan builds. Switch it any day from the Today screen.
            </p>
            <div className="onboarding__modes" role="radiogroup" aria-label="Today I'm">
              {HIKER_MODE_VALUES.map((offered) => (
                <button
                  key={offered}
                  type="button"
                  role="radio"
                  aria-checked={offered === mode}
                  className={
                    offered === mode
                      ? 'onboarding__mode onboarding__mode--on'
                      : 'onboarding__mode'
                  }
                  onClick={() => setMode(offered)}
                >
                  <ModeIcon mode={offered} size={22} className="onboarding__mode-icon" />
                  <span className="onboarding__mode-text">
                    <span className="onboarding__mode-name">
                      {HIKER_MODE_LABELS[offered]}
                    </span>
                    <span className="onboarding__mode-note">{MODE_NOTES[offered]}</span>
                  </span>
                </button>
              ))}
            </div>
          </section>
        )}

        {/* Where the hiker hikes (#1373, the design's frame 1b). A place,
            not a permission: the map has somewhere to open before location
            is asked for, and somewhere to fall back to whenever GPS has no
            fix. The sentence under the field is the promise
            lib/defaultPlace.ts and lib/userPreferences.ts keep: a place
            named from a published index, kept with the synced preferences
            since the maintainer's decision of 2026-09-10, and never a fix. */}
        {step.id === 'default-place' && (
          <section className="onboarding__step">
            <h1 className="onboarding__title">Where do you hike?</h1>
            <p>
              So we can put a trail in front of you before you turn location on &mdash;
              and fall back to it whenever GPS cannot get a fix.
            </p>
            <PlaceField
              places={places}
              settled={placesSettled}
              online={online}
              units={units}
              picked={place}
              onPick={setPlace}
              label="Where do you hike"
            />
            <p className="onboarding__reassurance">
              Kept with your settings &mdash; on this phone, and with your account once
              you sign in, so another device opens here too. Change it any time in More
              &rarr; You.
            </p>
          </section>
        )}

        {step.id === 'map-size' && (
          <section className="onboarding__step">
            <h1 className="onboarding__title">Take the whole trail with you</h1>
            <p>
              One download and the map is yours &mdash; no bars, no data plan, no
              surprises at the trailhead. Pick how much detail you want; you can change
              this later.
            </p>

            {SHEET_TABS.length > 1 ? (
              <Tabs
                label="Background maps"
                tabs={SHEET_TABS}
                activeId={openSheetId}
                onSelect={setOpenSheetId}
                idPrefix="onboarding-sheet"
              >
                {sheetPanel}
              </Tabs>
            ) : (
              sheetPanel
            )}
          </section>
        )}

        {step.id === 'location-permission' && (
          <section className="onboarding__step">
            <h1 className="onboarding__title">Show where you are on it?</h1>
            <p>
              Location is read on this phone and never sent anywhere. Without it the map
              still works &mdash; it just cannot tell you which side of the ridge you are
              on.
            </p>
            <div className="onboarding__actions">
              <button
                type="button"
                className="onboarding__primary"
                onClick={() => finish(true)}
              >
                Turn on location
              </button>
              {/* The fallback, named (frame 1d): declining is a choice of
                  what the map opens on instead, and where a place was given
                  the button says so rather than "Not now". */}
              <button
                type="button"
                className="onboarding__secondary"
                onClick={() => finish(false)}
              >
                {place === null ? 'Not now' : `Use ${place.name} instead`}
              </button>
            </div>
          </section>
        )}

        {downloadActivity !== null && <DownloadPanel activity={downloadActivity} />}

        {/* Each card's own pair (#1373, the design's F1): a primary that says
            what it does and a skip that says what skipping means. The
            location card carries its pair inside the step, since both of
            its buttons finish the flow. */}
        <div className="onboarding__nav">
          {step.id === 'what-ourhike-is' && (
            <>
              <button type="button" className="onboarding__primary" onClick={next}>
                Get set up
              </button>
              {/* Straight to the map, with every default: the standard
                  sheet still offered from Today, no place, no location. */}
              <button
                type="button"
                className="onboarding__skip"
                onClick={() => finish(false)}
              >
                Skip &mdash; take me to the map
              </button>
            </>
          )}
          {step.id === 'hiker-mode' && (
            <>
              {/* Absent until a mode is taken, for the place card's reason
                  below; the skip is the way on and says what it means. */}
              {mode !== null && (
                <button type="button" className="onboarding__primary" onClick={next}>
                  Continue as {HIKER_MODE_LABELS[mode].toLowerCase()}
                </button>
              )}
              <button
                type="button"
                className="onboarding__skip"
                onClick={() => {
                  setMode(null)
                  next()
                }}
              >
                Skip &mdash; day hike for now, change it on Today
              </button>
            </>
          )}
          {step.id === 'default-place' && (
            <>
              {/* No primary until there is a place to use - a "Use" button
                  with nothing behind it would be the dead control D10
                  forbids, and the skip is the honest way on. */}
              {place !== null && (
                <button type="button" className="onboarding__primary" onClick={next}>
                  Use {place.name}
                </button>
              )}
              <button
                type="button"
                className="onboarding__skip"
                onClick={() => {
                  setPlace(null)
                  next()
                }}
              >
                Skip &mdash; I&rsquo;ll set this later
              </button>
            </>
          )}
          {step.id === 'map-size' && (
            <>
              {/* The step's own pair (#1054): the primary starts the
                  transfer it has just sized - and says how much, which is
                  the design's one change to it - the ghost declines it
                  without ceremony, and the Today screen holds the door open
                  for a phone that decided later. */}
              <button
                type="button"
                className="onboarding__primary"
                onClick={startDownloadAndGo}
              >
                {downloadLabel}
              </button>
              <button type="button" className="onboarding__skip" onClick={next}>
                Decide this later
              </button>
            </>
          )}
        </div>
      </div>
    </main>
  )
}
