// "Which app do you listen in?" - the list a podcast card shows the first
// time a hiker taps Listen or ↓, and More → Settings shows to change it
// (#1690, the maintainer's frames 2 and 4).

import { PODCAST_APPS, PODCAST_APP_NAMES, type PodcastApp } from '../lib/podcasts'
import { PodcastAppIcon } from './PodcastAppIcon'

export interface PodcastAppPickerProps {
  value: PodcastApp | null
  onPick: (app: PodcastApp) => void
}

export function PodcastAppPicker({ value, onPick }: PodcastAppPickerProps) {
  return (
    <ul className="podcast-app-picker" aria-label="Podcast apps">
      {PODCAST_APPS.map((app) => (
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
