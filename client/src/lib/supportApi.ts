// The support calls (#1876): read, choose, Stop, and the email switch.
//
// All three are `authedFetch`, and none is queued through the outbox: a
// support choice is a decision made with the hiker looking at the screen, so
// a failure comes straight back to it rather than retrying behind their
// back - deleteAccount's argument, for the same kind of act.
//
// Apart from lib/api.ts so that only the deferred support screens carry them;
// see the note above `SupportSummary` there.

import { apiFetch, authedFetch, type SupportSummary } from './api'
import type { PaidTier } from './support'

/** The signed-in account's support. `status: 'none'` when there is none. */
export async function fetchSupport(signal?: AbortSignal): Promise<SupportSummary> {
  const response = await authedFetch('/support/me', { method: 'GET', signal })
  return (await response.json()) as SupportSummary
}

/** What `PUT /me/support` answers. Exactly one of `checkout_url` and
 *  `emailed` carries the next step, chosen by `delivery`. */
export interface SupportChoiceReceipt {
  support: SupportSummary
  /** Where a website-app hiker goes to pay. Null for `delivery: 'email'`. */
  checkout_url: string | null
  /** Whether the setup link went out by email (the store apps' path). */
  emailed: boolean
}

export interface SupportChoiceRequest {
  amount_cents: PaidTier
  /** The hiker opted in to the yearly "where the money went" email. */
  accounting_email: boolean
  /**
   * `redirect` in the website app; `email` in the iOS and Android apps,
   * which may not link to a payment outside the store's own (see
   * lib/support.ts).
   */
  delivery: 'redirect' | 'email'
  /**
   * "Share usage statistics" is on on this phone. Off, the backend never
   * counts this choice's level, even before that answer reaches the account
   * (the fourth #1885 review: Settings says off "stops all of it").
   */
  usage_counts: boolean
}

/** Record a paid choice as `pending` and get the way to complete it. */
export async function chooseSupport(
  request: SupportChoiceRequest,
): Promise<SupportChoiceReceipt> {
  const response = await authedFetch('/support/me', {
    method: 'PUT',
    body: JSON.stringify(request),
  })
  return (await response.json()) as SupportChoiceReceipt
}

/** The "Emails about my support" switch. Answers the summary, as Stop does. */
export async function setSupportMail(on: boolean): Promise<SupportSummary> {
  const response = await authedFetch('/support/me/mail', {
    method: 'PUT',
    body: JSON.stringify({ support_emails: on }),
  })
  return (await response.json()) as SupportSummary
}

/** Ask for the recurring payment to stop. One call, no reason asked. */
export async function stopSupport(): Promise<SupportSummary> {
  const response = await authedFetch('/support/me/stop', { method: 'POST' })
  return (await response.json()) as SupportSummary
}

/**
 * Whether the server takes a paid choice now - the public total's
 * `accepting`. The day-5 ask opens only when it does: a required question
 * every answer to which fails would be worse than none (the fourth #1885
 * review). Never rejects; anything but a clear yes is no.
 */
export async function supportAccepting(signal?: AbortSignal): Promise<boolean> {
  try {
    const response = await apiFetch('/support/total', { method: 'GET', signal })
    const body = (await response.json()) as { accepting?: unknown }
    return body.accepting === true
  } catch {
    return false
  }
}
