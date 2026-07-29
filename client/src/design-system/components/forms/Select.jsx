import React from 'react';
export function Select({ label, options = [], value, onChange }) {
return (
<label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontFamily: 'var(--font-body)' }}>
{label && <span style={{ fontSize: 'var(--text-body-s)', fontWeight: 'var(--weight-semibold)', color: 'var(--fg-2)' }}>{label}</span>}
<select value={value} onChange={onChange} style={{ padding: '11px 14px', borderRadius: 'var(--radius-m)', border: '1px solid var(--border-2)', fontSize: 'var(--text-body)', color: 'var(--fg-1)', background: 'var(--white)', outline: 'none' }}>
{options.map((o) => <option key={o} value={o}>{o}</option>)}
</select>
</label>
);
}
