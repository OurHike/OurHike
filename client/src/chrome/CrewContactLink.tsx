// The club's own channel, wherever a crew is offered - the workday sheet and
// every row lib/workProjects.ts prints (#760, #1440).
//
// One component rather than two anchors because the rule about WHICH strings
// may become a link has to have one home (#1578): a reviewed row's
// `signup_contact` is promised as "a mailto: or tel: or https: string" by
// pipeline/lib/work_projects.py, and the sink checks it again, because a
// check that only exists at the far end is one a future second producer
// walks straight past. A contact that is none of those renders nothing -
// the same answer as no contact at all, since a link the phone would act on
// is worse than a row with no link.
//
// THE LINK IS AN INTRODUCTION, NOT AN ENROLMENT (VOLUNTEERING.md): it is the
// club's own channel, and nothing here renders a roster claim of its own
// invention.

import { isSafeContactLink, isSafeLink } from '../lib/safeLink'

export interface CrewContactLinkProps {
  /** The club's own channel, or absent. */
  contact: string | null
  className: string
}

export function CrewContactLink({ contact, className }: CrewContactLinkProps) {
  if (contact === null || !isSafeContactLink(contact)) return null

  // A page opens beside the app, as every other external link here does; an
  // address or a number hands off to the phone's own handler and gets no tab.
  const opensBeside = isSafeLink(contact) ? { target: '_blank', rel: 'noreferrer' } : {}

  return (
    <a className={className} href={contact} {...opensBeside}>
      Ask the crew about joining
    </a>
  )
}
