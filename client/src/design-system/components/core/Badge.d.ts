export interface BadgeProps {
  children: React.ReactNode;
  tone?: 'easy' | 'moderate' | 'strenuous' | 'info' | 'neutral';
}
export declare function Badge(props: BadgeProps): JSX.Element;
