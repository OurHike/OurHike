export interface LogoProps {
  /** Icon size in px; wordmark and gap scale proportionally from the 96px reference. */
  size?: number;
  /** Render only the icon (no wordmark) — for favicons, app icons, compact headers. */
  iconOnly?: boolean;
  style?: React.CSSProperties;
}
export declare function Logo(props: LogoProps): JSX.Element;
