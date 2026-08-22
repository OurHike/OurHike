// The card a place gets after it stops existing (#831).
//
// features/POI_IDENTITY.md §4 calls this the *fourth* existence state — beside
// FIELD_NOTES.md's live, reported-missing and disputed — and states what it is
// for: "a hiker's photos of a decommissioned shelter keep a card to live on,
// saying what happened to the place rather than vanishing."
//
// WHAT IT REPLACES IS NOT AN ERROR, IT IS NOTHING AT ALL
//
// Today a stored anchor pointing at a retired id renders no card. Not a
// message, not a blank card — `App.tsx`'s `selectedPoi` finds no POI and hands
// the shell null. So a hiker whose photos are on a water point ATC dropped last
// September taps it and the app appears to ignore them. That is the whole bug
// this component closes on the client side, and it is the side that matters
// most: on-device anchors are the ones no server-side reconciliation can ever
// reach.
//
// THE SENTENCE IS DERIVED, AND THAT IS THE POINT
//
// #831 and §4 are both explicit that the copy "cannot hard-code 'no longer in
// ATC's data'". Measured against the ledger 2026-08-22, the 93 retired rows
// come from TWO sources — `atc_csi` and `opentrail_at` — and opentrail is not
// the ATC at all. So the sentence is built from the tombstone's `source`
// through `sourceLabel`, the same map the live card's provenance line uses, and
// a source neither of them knows renders as its own id rather than as a guess.
//
// TWO CARDS, NOT ONE WITH A FLAG
//
// `PoiCard` is a pin-anchored dialog that rides a point the map is drawing, and
// a retired place has no pin: `poi_*.geojson` carries live rows only, by an
// invariant three separate consumers enforce. Threading "…but this one has no
// pin" through that component would put the branch inside every one of its
// placement, chip-strip, photo and reporting paths. This is a plain centred
// card instead, which is what a place with no position on the map can honestly
// be.

import { typeLabel } from './legendLabels'
import { whatHappened } from './removedPoiText'
import type { Tombstone } from '../lib/poiIdentity'

export interface RemovedPoiCardProps {
  tombstone: Tombstone
  /** Where the pointer leads, when one does — already resolved by the shell,
   *  which is the only layer holding the live waypoints. Null is the ordinary
   *  case and the honest one: all 93 tombstones today have no successor. */
  successorName?: string
  onOpenSuccessor?: () => void
  onClose: () => void
}

export function RemovedPoiCard({
  tombstone,
  successorName,
  onOpenSuccessor,
  onClose,
}: RemovedPoiCardProps) {
  const name = tombstone.name ?? `A ${typeLabel(tombstone.poiType).toLowerCase()}`

  return (
    <div className="removed-poi" role="dialog" aria-label="Removed waypoint">
      <button type="button" className="removed-poi__close" onClick={onClose}>
        <span className="visually-hidden">Close</span>
      </button>

      <h2 className="removed-poi__name">{name}</h2>
      <p className="removed-poi__what">{whatHappened(tombstone)}</p>

      {successorName !== undefined && onOpenSuccessor !== undefined ? (
        /* The merge case §4 describes: upstream folded two places into one,
           and the pointer is what re-anchors a hiker's photos. Offered as a
           way THERE rather than followed silently — a hiker who took photos
           of a shelter is owed the knowledge that the place they are looking
           at is now called something else. */
        <>
          <p className="removed-poi__moved">
            It was merged into <strong>{successorName}</strong>, which has whatever you
            saved here.
          </p>
          <button type="button" className="removed-poi__go" onClick={onOpenSuccessor}>
            Open {successorName}
          </button>
        </>
      ) : (
        /* The honest unknown, and the state every one of today's tombstones
           is in. NOT "we do not know what happened": the ledger knows the
           place was removed and knows nothing replaced it, and saying so
           plainly beats offering a nearby waypoint the resolver deliberately
           refuses to guess at. */
        <p className="removed-poi__gone">
          Nothing took its place. Anything you saved here is still yours and still on this
          phone.
        </p>
      )}

      <p className="removed-poi__where">
        Last known position {tombstone.lat.toFixed(4)}, {tombstone.lon.toFixed(4)}
      </p>
    </div>
  )
}
