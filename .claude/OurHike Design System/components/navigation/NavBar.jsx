import React from 'react';
import { Button } from '../core/Button.jsx';
export function NavBar({ links = ['Trails', 'Get Involved', 'Shop', 'About'], active }) {
return (
<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 32px', background: 'var(--pine-900)', fontFamily: 'var(--font-body)' }}>
<div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
<img src="../../assets/trail-blaze-logo.svg" style={{ width: 8, height: 28, objectFit: 'contain' }} />
<div style={{ color: 'var(--paper-0)', fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 20, letterSpacing: '-0.01em' }}>OurHike</div>
</div>
<div style={{ display: 'flex', gap: 28 }}>
{links.map((l) => (
<a key={l} href="#" style={{ color: l === active ? 'var(--blaze-yellow)' : 'var(--sage-200)', textDecoration: 'none', fontSize: 'var(--text-body-s)', fontWeight: 'var(--weight-semibold)', letterSpacing: 'var(--tracking-wide)', textTransform: 'uppercase' }}>{l}</a>
))}
</div>
<Button variant="secondary" size="s">Donate</Button>
</div>
);
}
