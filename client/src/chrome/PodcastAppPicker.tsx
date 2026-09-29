// "Which app do you listen in?" - the list a podcast card shows the first
// time a hiker taps Listen or ↓, and More → Settings shows to change it
// (#1690, the maintainer's frames 2 and 4).

import { PODCAST_APP_NAMES, podcastAppsToList, type PodcastApp } from '../lib/podcasts'
import { PodcastAppIcon } from './PodcastAppIcon'

export interface PodcastAppPickerProps {
  value: PodcastApp | null
  onPick: (app: PodcastApp) => void
  /** The apps on offer - lib/podcasts.ts's appsEveryEpisodeOpensIn, so an
   *  app appears only once every episode opens in it. */
  apps: readonly PodcastApp[]
}

export function PodcastAppPicker({ value, onPick, apps }: PodcastAppPickerProps) {
  return (
    <ul className="podcast-app-picker" aria-label="Podcast apps">
      {podcastAppsToList(apps, value).map((app) => (
        <li key={app}>
          <button
            type="button"
            className="podcast-app-picker__app"
            aria-pressed={value === app}
            onClick={() => onPick(app)}
          >
            <PodcastAppIcon app={app} />
            <span>{PODCAST_APP_NAMES[app]}</span>
            {value === app && (
              <span className="podcast-app-picker__chosen" aria-hidden="true">
                ✓
              </span>
            )}
          </button>
        </li>
      ))}
    </ul>
  )
}
