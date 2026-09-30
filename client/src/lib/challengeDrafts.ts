// What a challenge sends, and nothing more (#1780, features/CHALLENGES.md,
// design principle 6: "nothing leaves the phone except queued tags (item id +
// authored time) and, only when the hiker sends it, one entry").
//
// In a module of their own rather than inside lib/outbox.ts, because
// backend/tests/test_client_report_contract.py reads outbox.ts as text to
// hold the report vocabulary to the server's, and two more literal unions
// there would be two more things for its regexes to mistake for a report
// field.

/** One completed challenge item. The outbox item's id is the server's
 *  idempotency key and its `authoredAt` the moment of the tag, so neither is
 *  repeated here. No coordinate, no mile, no register line. */
export interface ChallengeTagDraft {
  challenge_id: string
  item_id: string
  how: 'gps' | 'hand'
}

/**
 * The one entry a hiker chooses to send a club, at the finish.
 *
 * Name, one way to reach them, and the ids of what they tagged - what the
 * club receives, listed on the screen before the hiker sends it. For a
 * physical reward the club needs a mailing address; for a drawing, an email.
 * `finished_only` is the no-reward challenge's "let the club know you
 * finished": a name and nothing else.
 */
export interface ChallengeEntryDraft {
  challenge_id: string
  name: string
  email?: string
  mailing_address?: string
  item_ids: string[]
  consented: true
  finished_only?: boolean
}
