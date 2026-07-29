import React from 'react';
const sizes = { s: { padding: '8px 16px', fontSize: 'var(--text-body-s)' }, m: { padding: '11px 22px', fontSize: 'var(--text-body)' }, l: { padding: '14px 28px', fontSize: 'var(--text-body-l)' } };
const variants = {
primary: { background: 'var(--brand-primary)', color: 'var(--paper-0)', border: '1px solid var(--brand-primary)' },
secondary: { background: 'var(--blaze-orange)', color: 'var(--paper-0)', border: '1px solid var(--blaze-orange)' },
outline: { background: 'transparent', color: 'var(--brand-primary)', border: '1px solid var(--border-2)' },
ghost: { background: 'transparent', color: 'var(--fg-2)', border: '1px solid transparent' },
};
export function Button({ children, variant = 'primary', size = 'm', disabled = false, onClick, style }) {
const v = variants[variant] || variants.primary;
const s = sizes[size] || sizes.m;
const [hover, setHover] = React.useState(false);
const [active, setActive] = React.useState(false);
let bg = v.background;
if (!disabled && variant === 'primary') bg = active ? 'var(--brand-primary-press)' : hover ? 'var(--brand-primary-hover)' : v.background;
if (!disabled && variant === 'secondary') bg = active || hover ? 'var(--brand-secondary-hover)' : v.background;
if (!disabled && variant === 'outline') bg = hover ? 'var(--sage-100)' : v.background;
if (!disabled && variant === 'ghost') bg = hover ? 'var(--sage-100)' : v.background;
return (
<button
onClick={disabled ? undefined : onClick}
onMouseEnter={() => setHover(true)}
onMouseLeave={() => { setHover(false); setActive(false); }}
onMouseDown={() => setActive(true)}
onMouseUp={() => setActive(false)}
disabled={disabled}
style={{
fontFamily: 'var(--font-body)', fontWeight: 'var(--weight-semibold)', borderRadius: 'var(--radius-pill)',
cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.45 : 1, transition: 'background var(--duration-fast) var(--ease-standard), transform var(--duration-fast) var(--ease-standard)',
transform: active && !disabled ? 'scale(0.97)' : 'scale(1)', display: 'inline-flex', alignItems: 'center', gap: 8, ...s, ...v, background: bg, ...style,
}}
>{children}</button>
);
}
