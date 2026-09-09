// Find a hike (#1284): the search a hiker reaches from the Today shelf's
// "Find a hike" row. Pushed from Today, so Today stays the selected tab -
// this is not a fifth tab, and the shell keeps its TabBar under it.
//
// Three screens of the design in one component, because they are one
// search in two states and a sheet over it:
//
//   find     - the crumb back to Today, the search field, the facet chips,
//              and the results as they stand under a rule naming where the
//              search is anchored.
//   results  - pushed by a sheet's "Show N hikes": the count as the title,
//              the sort control, the applied filters as removable chips, and
//              the first result promoted to a full-bleed card.
//   a sheet  - one facet at a time (chrome/FacetSheet.tsx), over either.
//
// WHAT THIS SCREEN MUST STAY HONEST ABOUT, because a filter is a promise the
// list then keeps or breaks:
//
//  - Every count on a sheet is the number the list will then show
//    (lib/suggestedHikes.ts's `facetCounts`), computed over the same routes
//    the list is drawn from. FindHike.test.tsx asserts the two agree.
//  - No dead controls. A facet nothing on the phone can answer is not a chip;
//    a sort that cannot be honest is not offered; "Near me" exists only while
//    there is a fix. A list with one honest sort prints the sort as a word,
//    not a control.
//  - Location orders, it never cuts (`findHikes`). "Near Pearisburg, VA" over
//    the list means the list runs outward from Pearisburg.
//  - Nothing here fetches on keystroke. The search field resolves against
//    the towns and trailheads the phone already holds, and the routes come
//    from what it holds too - the last published document that reached it.
//  - No downloaded routes is a boundary, not "no hikes here". The sentence
//    says where the boundary is.
//
// The detail a card would open (wireframe `1g`) and the map view (`1h`) are
// not designed yet: the cards are articles until they are (SuggestedHikeCard
// says why), and "See these on the map" is not drawn because it would go
// nowhere.

import { useCallback, useMemo, useState } from 'react'
import { FacetSheet, type FacetSheetOption } from '../chrome/FacetSheet'
import { HikeFinderIcon } from '../chrome/HikeFinderIcon'
import { SuggestedHikeCard } from '../chrome/SuggestedHikeCard'
import type { PaceProfile } from '../lib/pace'
import {
  AUTHOR_KINDS,
  DIFFICULTIES,
  NO_FACETS,
  TIME_BUCKETS,
  anchorOf,
  appliedFilters,
  authorKindLabel,
  availableFacets,
  availableSorts,
  difficultyLabel,
  effectiveSort,
  facetCounts,
  facetIsSet,
  findHikes,
  publishersByKind,
  searchPlaces,
  sortLabel,
  timeBucketLabel,
  withoutFacet,
  withoutFilter,
  type AuthorKind,
  type Difficulty,
  type FacetId,
  type HikeFacets,
  type HikePlaceOption,
  type HikeSort,
  type SuggestedHike,
  type TimeBucket,
} from '../lib/suggestedHikes'
import type { LonLat } from '../lib/trailGraph'
import type { UnitSystem } from '../lib/units'
import '../chrome/chrome.css'
import './today.css'
import './findHike.css'

export interface FindHikeProps {
  /** Every published route the phone holds (lib/suggestedHikesData.ts). */
  hikes: readonly SuggestedHike[]
  /** The towns and trailheads the search field can resolve
   *  (lib/suggestedHikes.ts's `hikePlaces`). */
  places: readonly HikePlaceOption[]
  /** The fix, or null - which is what decides whether "Near me" exists. */
  fixAt: LonLat | null
  units: UnitSystem
  pace: PaceProfile
  onBack: () => void
  /** Opens a route's detail. Omitted until wireframe `1g` is designed; the
   *  cards are then things to read rather than buttons that go nowhere. */
  onOpenHike?: (id: string) => void
}

type View = 'find' | 'results'
type OpenSheet = FacetId | 'sort' | null

const FACET_CHIP: Record<FacetId, string> = {
  difficulty: 'Difficulty',
  time: 'Time',
  transit: 'Transit',
  author: 'Author',
}

export function FindHike({
  hikes,
  places,
  fixAt,
  units,
  pace,
  onBack,
  onOpenHike,
}: FindHikeProps) {
  const [facets, setFacets] = useState<HikeFacets>(NO_FACETS)
  const [view, setView] = useState<View>('find')
  const [open, setOpen] = useState<OpenSheet>(null)
  // The sheet's pending facets - what the counts are taken over while the
  // hiker is still deciding. Committed by "Show", discarded by closing.
  const [draft, setDraft] = useState<HikeFacets>(NO_FACETS)
  const [query, setQuery] = useState('')

  // Memoized like Today's journal (#1090): this screen is mounted while the
  // GPS clock and the 60-second clock re-render the shell above it, and the
  // list is rebuilt only when the routes, the facets or the fix move.
  const anchor = anchorOf(facets, fixAt)
  const sorts = useMemo(() => availableSorts(hikes, anchor, pace), [hikes, anchor, pace])
  const sort = effectiveSort(facets.sort, sorts)
  const results = useMemo(
    () => findHikes(hikes, facets, pace, fixAt),
    [hikes, facets, pace, fixAt],
  )
  const offeredFacets = useMemo(() => availableFacets(hikes, pace), [hikes, pace])
  const publishers = useMemo(() => publishersByKind(hikes), [hikes])
  const draftCounts = useMemo(
    () => (open === null || open === 'sort' ? null : facetCounts(hikes, draft, pace)),
    [open, hikes, draft, pace],
  )
  const draftResultCount = useMemo(
    () =>
      open === null || open === 'sort' ? 0 : findHikes(hikes, draft, pace, fixAt).length,
    [open, hikes, draft, pace, fixAt],
  )
  const placeMatches = useMemo(
    () =>
      // Nothing under the field once the text IS the picked place.
      facets.place !== null && query === facets.place.label
        ? []
        : searchPlaces(places, query),
    [places, query, facets.place],
  )
  const chips = appliedFilters(facets)

  const openSheet = (facet: FacetId) => {
    setDraft(facets)
    setOpen(facet)
  }
  const closeSheet = useCallback(() => setOpen(null), [])
  const showDraft = () => {
    setFacets(draft)
    setOpen(null)
    setView('results')
  }
  const clearFacet = (facet: FacetId) => {
    setFacets((current) => withoutFacet(current, facet))
    setOpen(null)
  }
  const toggleDraft = (facet: FacetId, id: string) => {
    setDraft((current) => {
      switch (facet) {
        case 'difficulty': {
          const level = id as Difficulty
          return {
            ...current,
            difficulty: current.difficulty.includes(level)
              ? current.difficulty.filter((d) => d !== level)
              : [...current.difficulty, level],
          }
        }
        case 'time':
          return { ...current, time: current.time === id ? null : (id as TimeBucket) }
        case 'transit':
          return { ...current, transitOnly: !current.transitOnly }
        case 'author': {
          const kind = id as AuthorKind
          return {
            ...current,
            authors: current.authors.includes(kind)
              ? current.authors.filter((a) => a !== kind)
              : [...current.authors, kind],
          }
        }
      }
    })
  }
  const pickPlace = (place: HikePlaceOption) => {
    setFacets((current) => ({ ...current, place: { label: place.name, at: place.at } }))
    setQuery(place.name)
  }
  const nearMe = () => {
    setFacets((current) => ({ ...current, place: null }))
    setQuery('')
  }

  // Where the search is anchored, said over the list. "Near you" only while
  // there is a fix to be near; otherwise the list is simply what the phone
  // holds, and the rule says that rather than claiming a place.
  const ruleLabel =
    facets.place !== null
      ? `Near ${facets.place.label}`
      : fixAt !== null
        ? 'Near you'
        : 'Routes on this phone'

  let sheet: React.ReactNode = null
  if (open === 'sort') {
    sheet = (
      <FacetSheet
        title="Order these by"
        options={sorts.map((candidate) => ({
          id: candidate,
          label: sortLabel(candidate),
          selected: candidate === sort,
        }))}
        onToggle={(id) => {
          setFacets((current) => ({ ...current, sort: id as HikeSort }))
          setOpen(null)
        }}
        onClose={closeSheet}
      />
    )
  } else if (open !== null && draftCounts !== null) {
    let title = ''
    let aside: string | undefined
    let caveat = ''
    let options: FacetSheetOption[] = []
    switch (open) {
      case 'difficulty':
        title = 'Difficulty'
        aside = 'the publisher’s rating'
        caveat = 'Quoted from whoever published the route — never rated by the app.'
        options = DIFFICULTIES.map((level) => ({
          id: level,
          label: difficultyLabel(level),
          count: draftCounts.difficulty[level],
          selected: draft.difficulty.includes(level),
        }))
        break
      case 'time':
        title = 'Time to complete'
        aside = 'at your pace'
        caveat =
          'Walking durations from distance and climb at your own pace — never an arrival time. A route whose climb nobody measured is listed without one.'
        options = TIME_BUCKETS.map((bucket) => ({
          id: bucket,
          label: timeBucketLabel(bucket),
          count: draftCounts.time[bucket],
          selected: draft.time === bucket,
        }))
        break
      case 'transit':
        title = 'Public transport'
        aside = 'as published'
        caveat =
          'Transit as the publisher listed it — a line and a walk, not a journey planner. Check before traveling.'
        options = [
          {
            id: 'transit',
            label: 'Reachable by public transport',
            count: draftCounts.transit,
            selected: draft.transitOnly,
          },
        ]
        break
      case 'author':
        title = 'Who wrote it'
        caveat =
          'The app surfaces routes and names who published them. It never ranks the publishers.'
        options = AUTHOR_KINDS.map((kind) => ({
          id: kind,
          label: authorKindLabel(kind),
          ...(publishers[kind].length > 0 ? { note: publishers[kind].join(' · ') } : {}),
          count: draftCounts.authors[kind],
          selected: draft.authors.includes(kind),
        }))
        break
    }
    const facet = open
    sheet = (
      <FacetSheet
        title={title}
        {...(aside === undefined ? {} : { aside })}
        options={options}
        onToggle={(id) => toggleDraft(facet, id)}
        caveat={caveat}
        showCount={draftResultCount}
        onClear={() => clearFacet(facet)}
        onShow={showDraft}
        onClose={closeSheet}
      />
    )
  }

  const count = results.length
  const empty =
    hikes.length === 0
      ? 'Nothing published reaches this phone yet — only routes inside what you have downloaded can be searched with no signal.'
      : count === 0
        ? 'Nothing on this phone matches all of these. Drop a filter to widen it.'
        : null

  return (
    <div className="find-hike">
      {view === 'find' ? (
        <header className="find-hike__head">
          <div className="find-hike__crumb-row">
            <button type="button" className="find-hike__crumb" onClick={onBack}>
              ‹ Today
            </button>
            <h1 className="find-hike__title">Find a hike</h1>
          </div>

          {/* Identical to chrome.css's .search__input, with the glass inside
              it. Resolves against the phone, never the network. */}
          <label className="find-hike__search">
            <HikeFinderIcon name="search" className="find-hike__search-icon" />
            <span className="visually-hidden">Where</span>
            <input
              className="find-hike__search-input"
              type="search"
              placeholder="Town, trailhead, or near me"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              autoComplete="off"
            />
          </label>
          {placeMatches.length > 0 && (
            <ul className="find-hike__places" aria-label="Places">
              {placeMatches.map((place) => (
                <li key={place.id}>
                  <button
                    type="button"
                    className="find-hike__place"
                    onClick={() => pickPlace(place)}
                  >
                    <span>{place.name}</span>
                    <span className="find-hike__place-kind">
                      {place.kind === 'town' ? 'Town' : 'Trailhead'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {(fixAt !== null || offeredFacets.length > 0) && (
            <div className="find-hike__chips">
              {/* Only while there is a fix: a "Near me" with nowhere to be
                  near would be a chip that does nothing. */}
              {fixAt !== null && (
                <button
                  type="button"
                  className={
                    facets.place === null
                      ? 'find-hike__chip find-hike__chip--set'
                      : 'find-hike__chip'
                  }
                  aria-pressed={facets.place === null}
                  onClick={nearMe}
                >
                  <HikeFinderIcon name="locate-fixed" className="find-hike__chip-icon" />
                  Near me
                </button>
              )}
              {offeredFacets.map((facet) => (
                <button
                  key={facet}
                  type="button"
                  className={
                    facetIsSet(facets, facet)
                      ? 'find-hike__chip find-hike__chip--set'
                      : 'find-hike__chip'
                  }
                  aria-haspopup="dialog"
                  onClick={() => openSheet(facet)}
                >
                  {FACET_CHIP[facet]} ▾
                </button>
              ))}
            </div>
          )}
        </header>
      ) : (
        <header className="find-hike__head find-hike__head--results">
          <div className="find-hike__crumb-row">
            <button
              type="button"
              className="find-hike__crumb"
              onClick={() => setView('find')}
            >
              ‹ Find
            </button>
            <h1 className="find-hike__title find-hike__title--count">
              {count === 1 ? '1 hike' : `${count} hikes`}
            </h1>
            {/* A control only where there is a choice; a single honest sort
                is a word, and none is silence. */}
            {sorts.length > 1 && sort !== null ? (
              <button
                type="button"
                className="find-hike__sort"
                aria-haspopup="dialog"
                onClick={() => setOpen('sort')}
              >
                {sortLabel(sort)} ▾
              </button>
            ) : sort !== null ? (
              <span className="find-hike__sort find-hike__sort--word">
                {sortLabel(sort)}
              </span>
            ) : null}
          </div>
          <div className="find-hike__chips">
            {chips.map((chip) => (
              <button
                key={`${chip.facet}:${chip.id}`}
                type="button"
                className="find-hike__chip find-hike__chip--set"
                onClick={() => setFacets((current) => withoutFilter(current, chip))}
              >
                {chip.label} <span aria-hidden="true">✕</span>
                <span className="visually-hidden">, remove</span>
              </button>
            ))}
            <button
              type="button"
              className="find-hike__chip find-hike__chip--add"
              onClick={() => setView('find')}
            >
              + filter
            </button>
          </div>
        </header>
      )}

      <div className="find-hike__body">
        {view === 'find' && hikes.length > 0 && (
          <div className="today__rule">
            <span className="today__rule-label">{ruleLabel}</span>
          </div>
        )}

        {results.map((hike, index) => (
          <SuggestedHikeCard
            key={hike.id}
            hike={hike}
            variant={view === 'results' && index === 0 ? 'hero' : 'row'}
            units={units}
            pace={pace}
            {...(onOpenHike === undefined ? {} : { onOpen: onOpenHike })}
          />
        ))}

        {empty !== null && <p className="find-hike__note">{empty}</p>}

        {view === 'results' && results.some((hike) => hike.transit !== undefined) && (
          <p className="find-hike__footer">Transit as the publisher listed it</p>
        )}

        {hikes.length > 0 && (
          <p className="find-hike__note">
            Only routes inside what you have downloaded can be searched with no signal.
          </p>
        )}
      </div>

      {sheet}
    </div>
  )
}
