// "Who looks after this stretch?" - the client's half of
// features/SAYING_THANKS.md's resolution.
//
// This is a nicety, not a dependency. The authoritative answer is worked out
// server-side when the thanks is finally received, from its `mile` and its
// authored date - which is the only place it CAN happen, because the normal
// case is composing a thanks with no signal. All this does is let the form
// say who a stretch belongs to when the phone happens to be online.
//
// **That was a promise rather than a description until #249**, and it is
// worth saying so here because this comment is what made it look done.
// `create_report` stored `maintainer_id`/`club_id` exactly as submitted and
// resolved nothing; it could not have resolved anyway, because a report
// carried no mile to resolve against (#244); and `club_only` appeared in no
// query, so a thanks reached its own author and nobody else. What the server
// does now: resolves what the hiker left blank, from the mile this form
// sends and the authored date, against the assignments effective then - and
// delivers by re-asking the same question at read time, so a stretch two
// maintainers share reaches both rather than neither.
//
// Every failure path here returns an empty list instead of throwing. A
// network error must never become an obstacle between someone and saying
// thank you - and losing the preview costs nothing now that the server does
// the resolution for real.

export interface MaintainerAssignment {
  id: string
  maintainer_id: string
  club_id: string
  club_name: string
  /** Null unless this maintainer opted in to being publicly creditable. */
  display_name: string | null
  start_mile: number
  end_mile: number
  effective_from: string
  effective_to: string | null
}

export async function lookupMaintainers(
  mile: number,
  authoredAt: Date,
): Promise<MaintainerAssignment[]> {
  // The authored date, never today's. A thanks written in June about a
  // section reassigned in July belongs to June's maintainer even when it
  // syncs in August.
  const asOf = authoredAt.toISOString().slice(0, 10)
  const url = `/maintainer-assignments?mile=${mile}&as_of=${asOf}`

  try {
    const response = await fetch(url)
    if (!response.ok) return []
    return (await response.json()) as MaintainerAssignment[]
  } catch {
    return []
  }
}

/**
 * One line naming who looks after a stretch, or null when nobody is assigned.
 *
 * Null rather than "Maintainer: unknown" on purpose - a thanks with no
 * resolved steward is still a complete thanks, and labelling it unknown makes
 * it feel like something is missing when nothing is.
 */
export function describeStewards(assignments: MaintainerAssignment[]): string | null {
  if (assignments.length === 0) return null

  // An opted-in individual is named with their club; everyone else is
  // represented by their club alone (SAYING_THANKS.md's privacy default).
  const names = assignments.map((a) =>
    a.display_name === null ? a.club_name : `${a.display_name} (${a.club_name})`,
  )
  const unique = [...new Set(names)]

  if (unique.length === 1) return `Looked after by ${unique[0]}`
  return `Looked after by ${unique.slice(0, -1).join(', ')} and ${unique.at(-1)}`
}
