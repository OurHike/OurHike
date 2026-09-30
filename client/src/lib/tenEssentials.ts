// The Ten Essentials checklist on the Plan tab, and where its gear links go
// (#1689).
//
// WHAT THIS IS FOR, IN ORDER. First a checklist: ten things to have in the
// pack before walking away from the car, ticked on this phone. Second a door
// to REI's category page for each one, which carries OurHike's affiliate code
// once there is one, and earns a commission on what a hiker buys there. The
// order matters. The list has to be worth opening for a hiker who never buys
// anything, because a page that is only a shop front is an advert inside a
// safety app.
//
// THE LIST ITSELF is the Mountaineers' "systems" version, as REI's Expert
// Advice page carries it: navigation, a headlamp, sun protection, first aid,
// a knife, fire, emergency shelter, and extra food, water and clothes. The
// names follow that list. The one-line notes under each name are this file's
// own paraphrase of what each system covers, so they are reasoned rather than
// quoted. The navigation note says "not only a phone" on purpose: this app is
// a phone, and a checklist inside it that let a hiker tick navigation for
// having the app would be the display outrunning its source.
//
// THE TRACKING BOUNDARY. OurHike itself tracks nothing here and adds no SDK
// (features/EVENTING.md lists cookies and third-party SDKs among the things
// the app never collects). An affiliate link does its tracking in the
// browser: tapping one sends the browser to the affiliate network, which
// records the visit and sets its cookie there, then forwards to REI. So this
// page is the whole of OurHike's affiliate surface, and nothing is tracked
// until a hiker taps one of its links. The maintainer chose that a tap goes
// straight to the browser, with the banner at the head of the page as the only
// disclosure (poll, 2026-09-26, frame D of the mock).

/** One of the ten, as the checklist stores and draws it. */
export interface Essential {
  /** Stable key in the stored checklist. Never reworded: a renamed id reads
   *  as unticked on every phone that ticked the old one. */
  id: EssentialId
  name: string
  /** What the system covers, in a line. */
  note: string
  /** REI's category page for it, as a path on www.rei.com. */
  reiPath: string
  /** What the link says to a screen reader: "Shop <this> at REI". */
  shopFor: string
}

export type EssentialId =
  | 'navigation'
  | 'headlamp'
  | 'sun'
  | 'first-aid'
  | 'knife'
  | 'fire'
  | 'shelter'
  | 'food'
  | 'water'
  | 'clothes'

/**
 * The ten, in the order the list is usually printed.
 *
 * THE REI PATHS ARE CATEGORY PAGES, never one product. A link to a specific
 * headlamp would be OurHike recommending that headlamp, on a safety list,
 * while earning a commission on it. A category page leaves the choice to the
 * hiker (the mock's own line, not objected to on 2026-09-26).
 *
 * Where each path came from: search-indexed REI page titles, read
 * 2026-09-26 ("Headlamps for Camping, Hiking & Running | REI Co-op" for
 * `/c/headlamps`, and so on). REI answered the sandbox with 403, so none of
 * them was loaded here. @unvalidated that each still resolves. A category REI
 * renames or retires lands the hiker on REI's own not-found page rather than
 * on a wrong product, which is the failure worth having. What would settle it:
 * tapping each link once on a phone, and again whenever REI reorganises its
 * catalogue.
 */
export const TEN_ESSENTIALS: readonly Essential[] = [
  {
    id: 'navigation',
    name: 'Navigation',
    note: 'Map and compass, not only a phone',
    reiPath: '/c/compasses',
    shopFor: 'compasses',
  },
  {
    id: 'headlamp',
    name: 'Headlamp',
    note: 'And spare batteries',
    reiPath: '/c/headlamps',
    shopFor: 'headlamps',
  },
  {
    id: 'sun',
    name: 'Sun protection',
    note: 'Sunglasses, sunscreen, a hat',
    reiPath: '/c/sun-protection',
    shopFor: 'sun protection',
  },
  {
    id: 'first-aid',
    name: 'First aid',
    note: 'Including blister care',
    reiPath: '/c/first-aid-kits',
    shopFor: 'first-aid kits',
  },
  {
    id: 'knife',
    name: 'Knife',
    note: 'Or a multi-tool, for repairs',
    reiPath: '/c/knives-and-tools',
    shopFor: 'knives and tools',
  },
  {
    id: 'fire',
    name: 'Fire',
    note: 'Matches or a lighter, and tinder',
    reiPath: '/c/fire-starting-gear',
    shopFor: 'fire-starting gear',
  },
  {
    id: 'shelter',
    name: 'Emergency shelter',
    note: 'A bivy or an emergency blanket',
    reiPath: '/c/emergency-shelter',
    shopFor: 'emergency shelter',
  },
  {
    id: 'food',
    name: 'Extra food',
    note: 'Beyond what you plan to eat',
    reiPath: '/c/backpacking-food',
    shopFor: 'backpacking food',
  },
  {
    id: 'water',
    name: 'Extra water',
    note: 'And a way to treat more',
    reiPath: '/c/portable-water-treatment',
    shopFor: 'water treatment',
  },
  {
    id: 'clothes',
    name: 'Extra clothes',
    note: 'Enough for a night out',
    reiPath: '/s/insulated-jackets-and-vests',
    shopFor: 'insulated jackets',
  },
]

const REI_ORIGIN = 'https://www.rei.com'

/**
 * OurHike's REI affiliate deep link, with `{url}` where the REI page goes, or
 * null for no affiliate code at all.
 *
 * NULL UNTIL THE MAINTAINER HAS AN ACCOUNT. Joining REI's program is an
 * application only the maintainer can make, and until there is a code the
 * links go to plain REI pages and the banner does not claim a commission.
 * A banner saying OurHike earns money on a link that earns nothing would be
 * a false statement on the one page that has to be straight about money.
 *
 * IN CODE RATHER THAN A BUILD VARIABLE, for the reason lib/supabase.ts's
 * ENABLED_PROVIDERS gives (#1572): an unset repository variable changes
 * what a build does silently, and nothing in a checkout can see it. The code
 * in an affiliate link is not a secret, since it travels in every link a
 * hiker taps. So changing it is a commit, reviewed like any other.
 *
 * The shape depends on the network. Third-party directories disagree on
 * whether REI runs its program through AvantLink or Impact (read 2026-09-26),
 * and both take a deep link with the destination URL-encoded into one
 * parameter. For example, AvantLink's
 * `https://www.avantlink.com/click.php?tt=cl&mi=<merchant>&pw=<site>&url={url}`.
 * The network's own dashboard is the source for the real one.
 */
export const REI_AFFILIATE_LINK: string | null = null

/**
 * Where one essential's link goes: REI's category page, sent through the
 * affiliate template when there is one.
 *
 * `template` defaults to the shipped constant and is a parameter so the
 * tests can hold the wrapped shape without shipping a code.
 */
export function reiLink(
  essential: Pick<Essential, 'reiPath'>,
  template: string | null = REI_AFFILIATE_LINK,
): string {
  const page = `${REI_ORIGIN}${essential.reiPath}`
  if (template === null) return page
  return template.replace('{url}', encodeURIComponent(page))
}

/**
 * Where the ticks are kept on this phone.
 *
 * ONE LIST PER HIKER, not one per hike (poll, 2026-09-26). The same ticks
 * show on every hike's Plan screen, and "Clear all" starts a fresh list
 * before the next trip.
 *
 * ITS OWN KEY, OUT OF THE SYNCED PREFERENCES, for lib/pace.ts's reason: the
 * preferences record is PUT whole to a backend that refuses unknown fields,
 * and a packing list is about this phone's owner on this trip rather than
 * something to follow them to a new phone.
 */
export const PACKED_ESSENTIALS_KEY = 'ourhike:ten-essentials'

const KNOWN_IDS: ReadonlySet<string> = new Set(TEN_ESSENTIALS.map((e) => e.id))

/** `localStorage`, or null where reaching for it throws: a browser set to
 *  block site data, or a WebView with storage off. */
function storage(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/**
 * The essentials ticked on this phone.
 *
 * Anything unreadable reads as nothing ticked, and an id this build does not
 * know is dropped. Unticked is the answer that sends a hiker to check their
 * pack. A guessed tick would tell them something is packed that nobody said.
 */
export function readPackedEssentials(): ReadonlySet<EssentialId> {
  let raw: string | null | undefined
  try {
    raw = storage()?.getItem(PACKED_ESSENTIALS_KEY)
  } catch {
    return new Set()
  }
  if (raw === null || raw === undefined) return new Set()
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return new Set()
    return new Set(
      parsed.filter(
        (id): id is EssentialId => typeof id === 'string' && KNOWN_IDS.has(id),
      ),
    )
  } catch {
    return new Set()
  }
}

/** Keeps the ticks, best-effort. A write that fails (quota, private mode)
 *  costs the ticks at the next launch and nothing else. */
export function writePackedEssentials(packed: ReadonlySet<EssentialId>): void {
  // In the list's own order, so the stored value does not depend on the
  // order a hiker happened to tick things in.
  const ids = TEN_ESSENTIALS.map((e) => e.id).filter((id) => packed.has(id))
  try {
    storage()?.setItem(PACKED_ESSENTIALS_KEY, JSON.stringify(ids))
  } catch {
    // See above.
  }
}
