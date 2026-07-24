import React from 'react';
const tones = {
easy: { bg: 'var(--sage-100)', fg: 'var(--forest-600)', border: 'var(--moss-300)' },
moderate: { bg: '#fbeed9', fg: '#8a5a1a', border: 'var(--blaze-yellow)' },
strenuous: { bg: '#f6e3cf', fg: 'var(--blaze-orange-dark)', border: 'var(--blaze-orange)' },
info: { bg: '#dbe7ef', fg: 'var(--blaze-blue)', border: 'var(--blaze-blue)' },
neutral: { bg: 'var(--stone-150)', fg: 'var(--stone-700)', border: 'var(--stone-300)' },
};
export function Badge({ children, tone = 'neutral' }) {
const t = tones[tone] || tones.neutral;
return (
<span style={{ display: 'inline-flex', alignItems: 'center', padding: '4px 12px', borderRadius: 'var(--radius-pill)', background: t.bg, color: t.fg, border: `1px solid ${t.border}`, fontFamily: 'var(--font-body)', fontSize: 'var(--text-caption)', fontWeight: 'var(--weight-semibold)', letterSpacing: 'var(--tracking-wide)', textTransform: 'uppercase' }}>{children}</span>
);
}
