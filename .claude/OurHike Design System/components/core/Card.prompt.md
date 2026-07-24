General-purpose content card, used for trail listings, blog/news teasers, and event tiles.

```jsx
<Card image={<img src="..." />} eyebrow="Harriman State Park" title="Suffern-Bear Mountain Trail"
  meta="7.2 mi · Strenuous · 4-5 hrs" footer={<Badge tone="strenuous">Strenuous</Badge>} />
```

Slots: `image` (16:9-ish top region), `eyebrow` (park/region label), `title` (display serif), `meta` (distance/time), `children` (free body), `footer` (divider + actions/badges).
