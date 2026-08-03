// The single place OurHike is allowed to send a push notification.
//
// The policy (features/HIKER_SAFETY.md §5, restated in FEATURES.md and
// WIREFRAMES.md): the wrong-way / off-trail alert is the ONLY notification
// this app ever sends. Serious warnings do not push. Weather does not push -
// HIKER_SAFETY.md flags whether it ever should as a genuinely open question
// and deliberately does not resolve it.
//
// The reason for a chokepoint rather than a convention: this rule erodes one
// well-meaning exception at a time. Each new "but this one is genuinely
// urgent" is defensible on its own, and the aggregate is an app that
// interrupts people on a mountain. Routing every push through one function
// means adding a second kind is a visible edit to this file, not a line
// somewhere else that nobody reviews as a policy change.
//
// lib/push.test.ts scans the source tree and fails if any other module
// touches a notification API directly.

export interface WrongWayAlert {
  title: string
  body: string
}

/**
 * The one permitted push. Named for its only caller on purpose - a generic
 * `sendPush(...)` would be an invitation.
 *
 * Delivered through the service worker registration rather than the
 * `Notification` constructor, because on the platform this actually ships to
 * the constructor does not work. Android Chrome throws outright - "Failed to
 * construct 'Notification': Illegal constructor. Use
 * ServiceWorkerRegistration.showNotification() instead" - and an installed
 * iOS PWA, the only place iOS delivers web push at all, has no usable
 * constructor either. Both want the registration.
 *
 * The constructor stays as the fallback because it is the path that works on
 * a desktop browser during development, which is where this gets looked at.
 */
export async function publishWrongWayAlert(alert: WrongWayAlert): Promise<boolean> {
  if (typeof Notification === 'undefined') return false
  if (Notification.permission !== 'granted') return false

  const options: NotificationOptions = { body: alert.body }

  if ('serviceWorker' in navigator) {
    try {
      // getRegistration(), not ready: `ready` never settles when nothing is
      // registered, and a promise that hangs forever is a worse failure than
      // a missed notification - it would leave the alert silently pending
      // for the rest of the hike with nothing to time it out.
      const registration = await navigator.serviceWorker.getRegistration()
      if (registration !== undefined) {
        await registration.showNotification(alert.title, options)
        return true
      }
    } catch {
      // Fall through: a registration that cannot show is not a reason to
      // give up on telling someone they are walking the wrong way.
    }
  }

  try {
    new Notification(alert.title, options)
    return true
  } catch {
    // Every path exhausted. Reported honestly rather than thrown: the caller
    // (lib/wrongWayAlert.ts) treats a false as "the cue is all we have", and
    // an exception here would take the in-app cue down with the push.
    return false
  }
}
