import React from 'react';
const tones = {
brand: { bg: 'var(--sage-100)', border: 'var(--moss-300)', fg: 'var(--pine-800)' },
urgent: { bg: '#f6e3cf', border: 'var(--blaze-orange)', fg: 'var(--blaze-orange-dark)' },
info: { bg: '#dbe7ef', border: 'var(--blaze-blue)', fg: 'var(--pine-900)' },
};
export function Callout({ title, children, tone = 'brand', action }) {
const t = tones[tone] || tones.brand;
return (
<div style={{ background: t.bg, border: `1px solid ${t.border}`, borderRadius: 'var(--radius-m)', padding: 'var(--space-5)', display: 'flex', flexDirection: 'column', gap: 8, fontFamily: 'var(--font-body)' }}>
{title && <div style={{ fontWeight: 'var(--weight-semibold)', color: t.fg, fontSize: 'var(--text-body-l)' }}>{title}</div>}
{children && <div style={{ color: 'var(--fg-2)', fontSize: 'var(--text-body)', lineHeight: 'var(--leading-normal)' }}>{children}</div>}
{action}
</div>
);
}
