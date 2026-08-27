// The source registry, as the org console reads it (#929).
//
// features/SOURCE_REGISTRY.md is the design. This is the read-only half of
// its admin surface, and the thing worth knowing before reading any of it is
// what it deliberately cannot do: NOTHING HERE CHANGES A HIKER'S MAP. There
// is no write path, no endpoint and no state - the console renders a
// published artifact and stops. That is SOURCE_REGISTRY.md's own property
// ("a person merging it is the only gate") held structurally rather than by
// discipline, and it is what makes an admin console safe to build before the
// backend that would one day write to it exists.
//
// WHY THIS IS NOT `stewards.json`. That artifact answers "whose data is on
// this phone" and may only ever name what actually ships - lib/stewards.ts
// and export_sources.py both carry the argument, which is credits.ts's rule:
// name what is actually there, never what could be. The console asks the
// opposite question, "what is registered, including what does not ship", so
// it reads its own file. Widening the first to answer the second would have
// put a held-back steward on a hiker's sources card.
//
// WHY IT IS FETCHED RATHER THAN DOWNLOADED. Every other artifact this app
// reads is copied into the offline bundle, because a hiker needs it on a
// ridge with no signal. This one is an admin screen read at a desk, and
// adding it to the download would spend a hiker's bytes and storage headroom
// on a table they will never open. So it is a plain fetch, and being offline
// renders "not now" rather than an error.

import { DATA_CONFIGURED, dataUrl } from './config'

/** One registered source, exactly as `pipeline/export_sources.py`'s
 *  `build_registry` writes it. Every field is one the registry already
 *  carries, copied - nothing here is composed, so nothing here is an opinion
 *  wearing the registry's authority. */
export interface RegisteredSource {
  key: string
  title: string | null
  provider: string
  /** The stable id (`org:nynjtc`), or null on a release built before #929. */
  steward_id: string | null
  steward: string | null
  /** Null where the registration declares none. That is twelve of the
   *  thirty-three, and it is the honest answer rather than the ArcGIS default
   *  `lib/source_registry.py` applies - a probe cannot describe a source
   *  whose kind nobody wrote down. */
  kind: string | null
  trust: string | null
  reaches_hikers: boolean
  /** What the licence rests on: the organization's own stated terms, the
   *  maintainer's authorisation (which is NOT a grant from the organization),
   *  or nothing yet. */
  licence_basis: string | null
  freshness_kind: string | null
  supports_donation: boolean
  /** Whether this organization has licensed its mark. `not_asked` on every
   *  row today. */
  mark_state: string | null
}

export interface RegisteredOrg {
  steward_id: string
  provider: string
  name: string | null
  note: string | null
}

export interface SourceRegistry {
  sources: readonly RegisteredSource[]
  organizations: readonly RegisteredOrg[]
}

export const EMPTY_REGISTRY: SourceRegistry = { sources: [], organizations: [] }

function str(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value : null
}

/**
 * The published artifact, read defensively.
 *
 * A row with no `key` is DROPPED, because the key is the only thing that makes
 * it a registration rather than a shape. Everything else about it may be
 * missing and the row still earns its place - a registration with no kind, no
 * trust and no licence basis is exactly the row an admin most needs to see.
 */
export function parseRegistry(value: unknown): SourceRegistry {
  const raw = value as { sources?: unknown; organizations?: unknown } | null | undefined

  const sources: RegisteredSource[] = []
  if (Array.isArray(raw?.sources)) {
    for (const entry of raw.sources) {
      const record = entry as Record<string, unknown> | null
      const key = str(record?.key)
      if (key === null) continue
      sources.push({
        key,
        title: str(record?.title),
        provider: str(record?.provider) ?? '',
        steward_id: str(record?.steward_id),
        steward: str(record?.steward),
        kind: str(record?.kind),
        trust: str(record?.trust),
        reaches_hikers: record?.reaches_hikers === true,
        licence_basis: str(record?.licence_basis),
        freshness_kind: str(record?.freshness_kind),
        supports_donation: record?.supports_donation === true,
        mark_state: str(record?.mark_state),
      })
    }
  }

  const organizations: RegisteredOrg[] = []
  if (Array.isArray(raw?.organizations)) {
    for (const entry of raw.organizations) {
      const record = entry as Record<string, unknown> | null
      const stewardId = str(record?.steward_id)
      if (stewardId === null) continue
      organizations.push({
        steward_id: stewardId,
        provider: str(record?.provider) ?? '',
        name: str(record?.name),
        note: str(record?.note),
      })
    }
  }

  return { sources, organizations }
}

/**
 * Fetch the registry, or null when it cannot be read.
 *
 * NULL RATHER THAN AN EMPTY REGISTRY, and the distinction is the whole of this
 * function's honesty: an empty registry means nothing is registered, and a
 * failed fetch means we could not ask. A console that rendered "0 sources" for
 * a phone that is offline would be making the first claim on the second's
 * evidence.
 */
export async function fetchRegistry(
  signal?: AbortSignal,
): Promise<SourceRegistry | null> {
  if (!DATA_CONFIGURED) return null
  try {
    const response = await fetch(dataUrl('registry.json'), { signal })
    if (!response.ok) return null
    return parseRegistry(await response.json())
  } catch {
    return null
  }
}

/** One organization's registered sources, grouped for the table. Sorted by
 *  how many sources each holds, then by name - the largest registration is
 *  the one an admin is most often looking for. */
export function byOrganization(
  registry: SourceRegistry,
): { org: RegisteredOrg | null; provider: string; sources: RegisteredSource[] }[] {
  const byId = new Map(registry.organizations.map((org) => [org.provider, org]))
  const grouped = new Map<string, RegisteredSource[]>()
  for (const source of registry.sources) {
    const list = grouped.get(source.provider)
    if (list === undefined) grouped.set(source.provider, [source])
    else list.push(source)
  }

  return [...grouped.entries()]
    .map(([provider, sources]) => ({
      provider,
      org: byId.get(provider) ?? null,
      sources,
    }))
    .sort(
      (a, b) =>
        b.sources.length - a.sources.length || a.provider.localeCompare(b.provider),
    )
}
