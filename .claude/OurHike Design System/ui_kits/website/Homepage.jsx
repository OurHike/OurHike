function Hero(){
const NS = window.OurHikeDesignSystem_60cee1;
const { Button } = NS;
return (
<div style={{background:'linear-gradient(180deg, var(--pine-800), var(--pine-900))',padding:'100px 32px 90px',display:'flex',flexDirection:'column',alignItems:'center',textAlign:'center',gap:20}}>
<div style={{color:'var(--sage-200)',fontFamily:'var(--font-body)',fontSize:'var(--text-eyebrow)',letterSpacing:'var(--tracking-eyebrow)',textTransform:'uppercase',fontWeight:600}}>Est. 1920 · Volunteer-Powered</div>
<div style={{color:'var(--paper-0)',fontFamily:'var(--font-display)',fontWeight:700,fontSize:'var(--text-display-xl)',lineHeight:'var(--leading-tight)',maxWidth:820}}>Blaze your path. Hike your own hike.</div>
<div style={{color:'var(--sage-200)',fontFamily:'var(--font-body)',fontSize:'var(--text-body-l)',maxWidth:560,lineHeight:'var(--leading-relaxed)'}}>Connect with the communities that build, maintain, and protect 2,100+ miles of public trails across New York and New Jersey.</div>
<div style={{display:'flex',gap:12,marginTop:8}}>
<Button variant="secondary" size="l">Find a Trail</Button>
<Button variant="outline" size="l" style={{color:'var(--paper-0)',borderColor:'var(--sage-200)'}}>Become a Member</Button>
</div>
</div>
);
}
function TrailGrid(){
const NS = window.OurHikeDesignSystem_60cee1;
const { Card, Badge } = NS;
const trails = [
{park:'Harriman State Park', name:'Suffern-Bear Mountain Trail', meta:'7.2 mi · 4–5 hrs', tone:'strenuous', label:'Strenuous'},
{park:'Ramapo Valley Reservation', name:'Darlington Schoolhouse Loop', meta:'2.1 mi · 1 hr', tone:'easy', label:'Easy'},
{park:'Norvin Green State Forest', name:'Wyanokie High Point', meta:'4.8 mi · 3 hrs', tone:'moderate', label:'Moderate'},
];
return (
<div style={{padding:'56px 32px',background:'var(--bg-page)'}}>
<div style={{maxWidth:1200,margin:'0 auto'}}>
<div style={{fontFamily:'var(--font-display)',fontSize:'var(--text-display-s)',color:'var(--fg-1)',marginBottom:24}}>Featured Trails</div>
<div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:20}}>
{trails.map((t)=>(
<Card key={t.name} image={<div style={{width:'100%',height:'100%',background:'linear-gradient(135deg,var(--sage-200),var(--moss-400))'}}/>} eyebrow={t.park} title={t.name} meta={t.meta} footer={<Badge tone={t.tone}>{t.label}</Badge>} />
))}
</div>
</div>
</div>
);
}
function MembershipCallout(){
const NS = window.OurHikeDesignSystem_60cee1;
const { Callout, Button } = NS;
return (
<div style={{padding:'0 32px 64px',background:'var(--bg-page)'}}>
<div style={{maxWidth:1200,margin:'0 auto'}}>
<Callout tone="brand" title="Support 2,100+ Miles of Trail" action={<Button variant="primary" size="m">Join Today</Button>}>
Membership starts at $25/year and funds trail crews, maps, and conservation programs across the region.
</Callout>
</div>
</div>
);
}
function Homepage(){
const NS = window.OurHikeDesignSystem_60cee1;
const { NavBar, Footer } = NS;
return (
<div style={{fontFamily:'var(--font-body)'}}>
<NavBar active="Trails" />
<Hero />
<TrailGrid />
<MembershipCallout />
<Footer />
</div>
);
}
window.Homepage = Homepage;
