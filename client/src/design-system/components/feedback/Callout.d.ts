export interface CalloutProps {
  title?: string;
  children?: React.ReactNode;
  tone?: 'brand' | 'urgent' | 'info';
  action?: React.ReactNode;
}
export declare function Callout(props: CalloutProps): JSX.Element;
