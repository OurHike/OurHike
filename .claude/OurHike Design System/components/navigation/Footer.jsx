import React from 'react';
export function Footer() {
const cols = [
{ h: 'Explore', items: ['Find a Trail', 'Maps & Guides', 'Trail Regions', 'Events'] },
{ h: 'Get Involved', items: ['Volunteer', 'Membership', 'Careers', 'Donate'] },
{ h: 'About', items: ['Our Mission', 'Board & Staff', 'Trail Walker Magazine', 'Contact'] },
];
return (
<div style={{ background: 'var(--pine-900)', color: 'var(--sage-200)', fontFamily: 'var(--font-body)', padding: '48px 32px 28px' }}>
<div style={{ display: 'flex', gap: 64, flexWrap: 'wrap', maxWidth: 1200, margin: '0 auto' }}>
<div style={{ minWidth: 220 }}>
<div style={{ color: 'var(--paper-0)', fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 22 }}>OurHike</div>
<div style={{ marginTop: 10, fontSize: 'var(--text-body-s)', lineHeight: 'var(--leading-relaxed)' }}>600 Ramapo Valley Rd<br/>Mahwah, NJ 07430</div>
</div>
{cols.map((c) => (
<div key={c.h}>
<div style={{ color: 'var(--paper-0)', fontWeight: 'var(--weight-semibold)', fontSize: 'var(--text-body-s)', textTransform: 'uppercase', letterSpacing: 'var(--tracking-wide)', marginBottom: 12 }}>{c.h}</div>
<div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
{c.items.map((i) => <a key={i} href="#" style={{ color: 'var(--sage-200)', textDecoration: 'none', fontSize: 'var(--text-body-s)' }}>{i}</a>)}
</div>
</div>
))}
</div>
<div style={{ borderTop: '1px solid var(--pine-700)', marginTop: 36, paddingTop: 18, fontSize: 'var(--text-caption)', maxWidth: 1200, margin: '36px auto 0' }}>© 2026 OurHike.</div>
</div>
);
}
