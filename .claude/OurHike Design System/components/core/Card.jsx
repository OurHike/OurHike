import React from 'react';
export function Card({ image, eyebrow, title, meta, children, footer }) {
return (
<div style={{ background: 'var(--surface-card)', borderRadius: 'var(--radius-l)', overflow: 'hidden', boxShadow: 'var(--shadow-card)', border: '1px solid var(--border-1)', display: 'flex', flexDirection: 'column', fontFamily: 'var(--font-body)' }}>
{image && <div style={{ height: 160, background: 'var(--sage-100)' }}>{image}</div>}
<div style={{ padding: 'var(--space-5)', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', flex: 1 }}>
{eyebrow && <div style={{ fontSize: 'var(--text-eyebrow)', letterSpacing: 'var(--tracking-eyebrow)', textTransform: 'uppercase', color: 'var(--forest-600)', fontWeight: 'var(--weight-semibold)' }}>{eyebrow}</div>}
{title && <div style={{ fontFamily: 'var(--font-display)', fontSize: 'var(--text-heading)', color: 'var(--fg-1)', lineHeight: 'var(--leading-snug)' }}>{title}</div>}
{meta && <div style={{ fontSize: 'var(--text-body-s)', color: 'var(--fg-3)' }}>{meta}</div>}
{children}
</div>
{footer && <div style={{ padding: 'var(--space-4) var(--space-5)', borderTop: '1px solid var(--border-1)' }}>{footer}</div>}
</div>
);
}
