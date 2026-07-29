export interface ButtonProps {
  children: React.ReactNode;
  /** Visual style */
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost';
  size?: 's' | 'm' | 'l';
  disabled?: boolean;
  onClick?: () => void;
  style?: React.CSSProperties;
}
export declare function Button(props: ButtonProps): JSX.Element;
