/**
 * The OurHike mark, in React.
 *
 * The same drawing as `site/src/components/Mark.astro` - the white blaze with
 * its edges roughened by a turbulence filter, over a ground split between
 * forest and stone - carried across rather than re-traced, because two hand
 * drawings of one mark drift and nobody notices which is wrong.
 *
 * `id` MUST BE UNIQUE PER INSTANCE. SVG filter and clip-path ids are
 * document-global, so two marks sharing them is fine right up until one of
 * them is inside something that gets unmounted and takes the `<defs>` with
 * it - at which point the other one renders as a plain square. The Astro
 * component carries the same warning for the same reason.
 *
 * The two hex values are the exception to the tokens-only rule, and it is the
 * same exception `Contours.astro` takes: this is pigment in a drawing rather
 * than chrome, it has to survive being rendered on paper and on pine alike,
 * and a mark that changed colour with the theme would stop being a mark.
 */
export function Mark({ size = 34, id }: { size?: number; id: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 96 96" role="img" aria-label="OurHike">
      <defs>
        <linearGradient id={`${id}-split`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="50%" stopColor="#355c3a" />
          <stop offset="50%" stopColor="#5a5346" />
        </linearGradient>
        <clipPath id={`${id}-round`}>
          <rect width="96" height="96" rx="20" />
        </clipPath>
        <filter id={`${id}-jag`} x="-40%" y="-15%" width="180%" height="130%">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.03 0.09"
            numOctaves="2"
            seed="7"
            result="n"
          />
          <feDisplacementMap
            in="SourceGraphic"
            in2="n"
            scale="10"
            xChannelSelector="R"
            yChannelSelector="G"
          />
        </filter>
      </defs>
      <g clipPath={`url(#${id}-round)`}>
        <rect width="96" height="96" fill={`url(#${id}-split)`} />
        <svg x="31" y="8" width="34" height="80" viewBox="0 0 40 100">
          <rect
            x="10"
            y="8"
            width="20"
            height="84"
            rx="10"
            fill="#fff"
            filter={`url(#${id}-jag)`}
          />
        </svg>
      </g>
    </svg>
  )
}
