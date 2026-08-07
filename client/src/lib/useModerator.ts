// Whether the signed-in person may moderate (#235).
//
// The client has never read a role. `Profile.role` has existed on the backend
// the whole time and `require_role(maintainer, club_admin)` gates all five
// moderation endpoints, but nothing here ever asked - so the queue screen had
// no way to know whether to offer itself.
//
// WHY THIS DEFAULTS TO "NO" AND STAYS THERE ON FAILURE
//
// The answer this hook gives decides whether an entry point appears, not
// whether anything is permitted: the backend is the thing enforcing the role,
// and it does so on every call regardless of what this returns. So the cost
// of the two wrong answers is asymmetric. A false "yes" offers a maintainer's
// screen to a hiker, who then gets a 403 they cannot act on and an app that
// looks broken. A false "no" hides a menu entry from a maintainer, who can
// reload. Unknown therefore reads as "no", including while the request is in
// flight and after it fails.
//
// One request, when an account appears - not a poll. A role changes when a
// club promotes somebody, which is a thing that happens once and is followed
// by a person being told about it, not something worth waking the radio for.

import { useEffect, useState } from 'react'
import { fetchMyProfile } from './api'

/** The roles the backend's moderation endpoints accept - `MODERATOR_ROLES` in
 *  backend/app/models/profile.py, mirrored rather than fetched.
 *
 *  A mirror can drift, which is why it is named here rather than inlined as a
 *  comparison: if a third moderating role is ever added, this is the one place
 *  the client has to learn about it, and the failure mode is a hidden menu
 *  entry rather than anything a hiker can reach. */
export const MODERATOR_ROLES = ['maintainer', 'club_admin'] as const

/**
 * True only when the signed-in account is known to be a moderator.
 *
 * `signedIn` gates the request rather than the hook being conditional, so a
 * sign-in mid-session asks and a sign-out forgets - without which someone
 * else's role would survive on a shared device until reload.
 */
export function useModerator(signedIn: boolean): boolean {
  const [moderator, setModerator] = useState(false)

  useEffect(() => {
    if (!signedIn) {
      setModerator(false)
      return
    }

    const controller = new AbortController()
    void fetchMyProfile(controller.signal)
      .then((profile) => {
        if (!controller.signal.aborted) {
          setModerator((MODERATOR_ROLES as readonly string[]).includes(profile.role))
        }
      })
      // No signal, a 401 on a token that expired, a backend that is not
      // configured at all. All of them mean the same thing here: we do not
      // know, so we do not offer.
      .catch(() => {})

    return () => controller.abort()
  }, [signedIn])

  return moderator
}
