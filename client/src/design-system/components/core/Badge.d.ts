export interface BadgeProps {
  children: React.ReactNode;
  /** The five difficulty tones are NYNJTC's own ladder (#1290), which the
   *  app adopted whole rather than collapsing the two compound levels into
   *  their neighbours - a route their steward called "easy to moderate" is
   *  not one they called easy. */
  tone?:
    | 'easy'
    | 'easy-moderate'
    | 'moderate'
    | 'moderate-strenuous'
    | 'strenuous'
    | 'info'
    | 'neutral';
}
export declare function Badge(props: BadgeProps): JSX.Element;
