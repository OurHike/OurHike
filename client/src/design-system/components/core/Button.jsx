import React from 'react';
/*
 * THE TWO FILLED VARIANTS TAKE `--fg-on-brand`, NOT `--paper-0` (#1131).
 *
 * Both used to hardcode `--paper-0`, and `secondary` used to read the BASE
 * token `--blaze-orange` rather than the semantic `--brand-secondary`. Two
 * bugs with one symptom, measured 2026-08-27 against tokens/colors.css:
 *
 *   secondary  paper-0 on blaze-orange   4.14:1 in BOTH themes
 *   primary    paper-0 on brand-primary  7.53:1 light, 3.42:1 dark
 *
 * AA wants 4.5:1, and `size="s"` is 14px, so the large-text exemption does
 * not apply. `--fg-on-brand` exists for exactly this and colors.css says so:
 * "a filled brand button is dark green under the light theme and pale moss
 * under the dark one, so what is legible on it is not the same colour."
 * A base token cannot follow a theme at all - colors.css is explicit that
 * base entries are never re-pointed - so `secondary` could not have been
 * fixed by changing the label alone.
 *
 * The pairs are asserted in Button.contrast.test.ts, computed from the token
 * file rather than from hex written down here.
 */
const sizes = { s: { padding: '8px 16px', fontSize: 'var(--text-body-s)' }, m: { padding: '11px 22px', fontSize: 'var(--text-body)' }, l: { padding: '14px 28px', fontSize: 'var(--text-body-l)' } };
const variants = {
primary: { background: 'var(--brand-primary)', color: 'var(--fg-on-brand)', border: '1px solid var(--brand-primary)' },
secondary: { background: 'var(--brand-secondary)', color: 'var(--fg-on-brand)', border: '1px solid var(--brand-secondary)' },
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
