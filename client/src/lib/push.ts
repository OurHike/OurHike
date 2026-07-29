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
 */
export async function publishWrongWayAlert(alert: WrongWayAlert): Promise<boolean> {
  if (typeof Notification === 'undefined') return false
  if (Notification.permission !== 'granted') return false

  new Notification(alert.title, { body: alert.body })
  return true
}
