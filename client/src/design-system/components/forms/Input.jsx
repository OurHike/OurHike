import React from 'react';
export function Input({ label, placeholder, type = 'text', value, onChange, error }) {
const [focus, setFocus] = React.useState(false);
return (
<label style={{ display: 'flex', flexDirection: 'column', gap: 6, fontFamily: 'var(--font-body)' }}>
{label && <span style={{ fontSize: 'var(--text-body-s)', fontWeight: 'var(--weight-semibold)', color: 'var(--fg-2)' }}>{label}</span>}
<input
type={type} placeholder={placeholder} value={value} onChange={onChange}
onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
style={{
padding: '11px 14px', borderRadius: 'var(--radius-m)', border: `1px solid ${error ? 'var(--danger)' : focus ? 'var(--brand-primary)' : 'var(--border-2)'}`,
boxShadow: focus ? 'var(--shadow-focus)' : 'none', fontSize: 'var(--text-body)', color: 'var(--fg-1)', background: 'var(--white)', outline: 'none', transition: 'border var(--duration-fast), box-shadow var(--duration-fast)',
}}
/>
{error && <span style={{ fontSize: 'var(--text-caption)', color: 'var(--danger)' }}>{error}</span>}
</label>
);
}
