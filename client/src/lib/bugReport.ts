// Reporting a bug in OurHike itself (#626).
//
// The forms already existed - `.github/ISSUE_TEMPLATE/bug_report.yml` for a
// defect in the software and `trail_data.yml` for a systematic data problem -
// and nothing in the app pointed at either, so the only way in was already
// knowing the project is on GitHub. This module is the half that can be
// tested without a screen: which form each option opens, and which of its
// fields are answered before the hiker gets there.
//
// WHY ANYTHING IS PREFILLED AT ALL. A bug report is worth about as much as the
// build it names, and lib/buildInfo.ts exists because seven characters of hex
// retyped off a phone screen arrive with a digit changed. Carrying the build
// in the URL means the fact arrives intact with nobody copying anything -
// the same job screens/AboutBuild.tsx's copy button does for the path where
// somebody writes an email instead.
//
// WHAT IS DELIBERATELY NOT PREFILLED: `navigator.userAgent`. It would answer
// the form's "phone and browser" question better than a hiker can, and it is
// still not ours to attach to a public issue on their behalf. The build is a
// fact about our software; the device is a fact about them, and this app does
// not put facts about them anywhere they did not choose to put them
// (IDENTITY_AND_PRIVACY.md). The form asks in words instead, which is answerable.

import { BUILD_INFO, buildSummary, type BuildInfo } from './buildInfo'

/** The repository, which every link here is built from. */
export const REPOSITORY_URL = 'https://github.com/OurHike/OurHike'

/** How this project plans work, for whoever wants to fix what they found. */
export const CONTRIBUTING_URL = `${REPOSITORY_URL}/blob/main/CONTRIBUTING.md`

/** Settled design, existing patterns - the label CONTRIBUTING.md points at. */
export const GOOD_FIRST_ISSUE_URL = `${REPOSITORY_URL}/labels/good%20first%20issue`

/**
 * The form for a defect in the software. Its `conditions` field is where the
 * build goes, and it is the only form that has one.
 */
const SOFTWARE_FORM = 'bug_report.yml'

/** The form for a data problem that will still be wrong next season. */
const DATA_FORM = 'trail_data.yml'

export interface BugReportOption {
  /** Stable across wording changes, so keys and tests do not ride on copy. */
  id: string
  /** What the row says. */
  label: string
  /** One line under it, saying which kind of thing belongs here. */
  hint: string
  /** Which form this opens, by filename in `.github/ISSUE_TEMPLATE/`. */
  template: string
  /**
   * The `area` dropdown option in bug_report.yml, VERBATIM, or null where the
   * form has no such field.
   *
   * GitHub matches a prefilled dropdown by its option TEXT, so a label
   * reworded in the form and not here does not fail loudly - it silently stops
   * preselecting, and the only symptom is reports arriving with no area on
   * them. test/issueFormPrefill.test.ts reads the form itself to catch that.
   */
  area: string | null
}

/**
 * The common options, in the order they are offered.
 *
 * Four, and worded for the person holding the phone rather than for the
 * tracker they land in: someone who has just watched a pin sit in the wrong
 * place is not thinking in terms of client, backend and pipeline. The mapping
 * onto those is what `template` and `area` are for, and it happens here so it
 * does not have to happen in the hiker's head.
 */
export const BUG_REPORT_OPTIONS: BugReportOption[] = [
  {
    id: 'app',
    label: 'The app itself',
    hint: 'A screen, a button, the map — something in OurHike does not do what it should.',
    template: SOFTWARE_FORM,
    area: 'Client — the map app',
  },
  {
    // Not a bug in the strict sense, and it belongs here anyway: it is the
    // most common thing a hiker actually wants to report about the app, and
    // leaving it out would send it to the option that fits worst. The hint
    // carries the distinction the trail_data.yml header makes - a systematic
    // problem, not a condition that will have changed by next week.
    id: 'data',
    label: 'Something on the map is wrong',
    hint: 'A shelter in the wrong place, a missing water source, a wrong blaze colour — wrong every day, not only today.',
    template: DATA_FORM,
    area: null,
  },
  {
    id: 'account',
    label: 'Reports, syncing or signing in',
    hint: 'A report that will not send, a sign-in that will not take, something that came back changed.',
    template: SOFTWARE_FORM,
    area: 'Backend — reports, closures, moderation, accounts',
  },
  {
    id: 'unsure',
    label: 'Something else',
    hint: 'Anything that does not fit the three above. Not knowing which it is, is fine.',
    template: SOFTWARE_FORM,
    area: 'Not sure',
  },
]

/**
 * Where an option goes, with what already answered.
 *
 * Pure and taking the build rather than reading it, for the reason
 * lib/buildInfo.ts gives about testing against a live commit.
 */
export function bugReportUrl(
  option: BugReportOption,
  build: BuildInfo = BUILD_INFO,
): string {
  const params = new URLSearchParams({ template: option.template })

  if (option.area !== null) params.set('area', option.area)

  // Only onto the form that has the field. GitHub ignores a parameter naming
  // no field, so sending it anyway would work and would still be a lie about
  // what the data form asks for.
  if (option.template === SOFTWARE_FORM) params.set('conditions', buildSummary(build))

  return `${REPOSITORY_URL}/issues/new?${params.toString()}`
}
