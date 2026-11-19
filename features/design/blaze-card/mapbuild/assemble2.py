"""Assemble the four blaze-card maps from the projected geometry.

The vocabulary is OurHike's own, reused rather than invented:
  - ground: the Field palette's wood/park greens on a paper page
    (features/MAP_STYLE_SPEC.md TOPO_PALETTE: wood #dcebd2, park #d3e6c6,
    parkEdge #5f8f57, water #8fc0dc, boundary #6f6753, label #14130f)
  - the trail: cased the way style.ts draws the A.T. - a #14130f casing
    under the line (trail casing #14130f), blaze-white #fdfaf2 inside
  - a challenge place: the diamond pin from map/challengePin.ts - the body is
    the diamond, CHALLENGE_COLOR #d69a2d, hollow until earned, filled with a
    tick when earned
  - walked miles: the yellow the app already uses for the taken stretch
  - mile ticks every 500 miles, labelled, so the A.T. mile is the axis
"""
import json, sys

PAPER = '#f7f3e9'      # --paper-100
PAGE = '#fffdf7'       # --paper-0 (MAP_BACKGROUND_COLOR is white; paper reads warmer on the card)
WOOD = '#dcebd2'
PARK = '#d3e6c6'
PARK_EDGE = '#5f8f57'
WATER = '#8fc0dc'
BOUNDARY = '#6f6753'
INK = '#14130f'
LABEL = '#14130f'
BLAZE_WHITE = '#fdfaf2'
BLAZE_YELLOW = '#d69a2d'
BLAZE_ORANGE = '#c1611a'
STONE_600 = '#706859'
MONO = "'IBM Plex Mono', monospace"


def diamond(x, y, r, earned, scale):
    """The challenge pin: a diamond with apothem r (challengePin.ts), paper
    hairline, hollow until earned; earned = filled yellow with the tick."""
    s = r * 1.4142
    pts = f'{x:.1f},{y - s:.1f} {x + s:.1f},{y:.1f} {x:.1f},{y + s:.1f} {x - s:.1f},{y:.1f}'
    if earned:
        tick = (f'<path d="M{x - r * 0.55:.1f} {y + r * 0.05:.1f} L{x - r * 0.12:.1f} {y + r * 0.5:.1f} L{x + r * 0.62:.1f} {y - r * 0.5:.1f}" '
                f'fill="none" stroke="{INK}" stroke-width="{max(1.4, r * 0.22):.1f}" stroke-linecap="round" stroke-linejoin="round"></path>')
        return (f'<polygon points="{pts}" fill="{BLAZE_YELLOW}" stroke="{PAGE}" stroke-width="{1.2 * scale:.1f}"></polygon>'
                f'<polygon points="{pts}" fill="none" stroke="{INK}" stroke-width="{0.8 * scale:.1f}" opacity="0.55"></polygon>{tick}')
    return (f'<polygon points="{pts}" fill="{PAGE}" stroke="{BLAZE_YELLOW}" stroke-width="{1.8 * scale:.1f}"></polygon>'
            f'<polygon points="{pts}" fill="none" stroke="{INK}" stroke-width="{0.6 * scale:.1f}" opacity="0.35"></polygon>')


def chosen_ring(x, y, scale):
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{15 * scale:.1f}" fill="none" stroke="{BLAZE_ORANGE}" stroke-width="{2 * scale:.1f}"></circle>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{24 * scale:.1f}" fill="none" stroke="{BLAZE_ORANGE}" stroke-width="{1.2 * scale:.1f}" opacity="0.45"></circle>')


def text(x, y, s, size, fill=LABEL, anchor='start', weight=400, halo=True):
    h = (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{MONO}" font-size="{size:.0f}" font-weight="{weight}" '
         f'fill="{PAGE}" stroke="{PAGE}" stroke-width="{size * 0.34:.1f}" stroke-linejoin="round" text-anchor="{anchor}">{s}</text>') if halo else ''
    return h + (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{MONO}" font-size="{size:.0f}" font-weight="{weight}" '
                f'fill="{fill}" text-anchor="{anchor}">{s}</text>')


def build(name, geom, *, earned, hollow, walked, scale=1.0, chosen=None, place_labels=(), hide_states=(),
          cluster_px=9, legend=True, counts=True, termini_miles=False, aria=''):
    d = json.load(open(geom))
    W, H = d['W'], d['H']
    out = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{aria}">')
    out.append(f'<rect width="{W}" height="{H}" fill="{WATER}" rx="{14 * scale:.0f}"></rect>')
    out.append(f'<path d="{d["canada"]}" fill="{WOOD}"></path>')
    out.append(f'<path d="{d["otherStates"]}" fill="{WOOD}"></path>')
    out.append(f'<path d="{d["atStates"]}" fill="{PARK}"></path>')
    out.append(f'<path d="{d["borders"]}" fill="none" stroke="{BOUNDARY}" stroke-width="{0.7 * scale:.1f}" opacity="0.55"></path>')
    # the fourteen trail states get a slightly stronger edge, the way parkEdge outlines a park
    out.append(f'<path d="{d["atStates"]}" fill="none" stroke="{PARK_EDGE}" stroke-width="{0.6 * scale:.1f}" opacity="0.5"></path>')
    for k, (x, y) in d['labels'].items():
        if k in hide_states or k in ('GA', 'ME') or not (12 < x < W - 12 and 12 < y < H - 12):
            continue
        out.append(text(x, y, k, 10 * scale, fill=STONE_600, anchor='middle', halo=False))
    # the trail: casing then blaze-white inside, as the app draws the A.T.
    out.append(f'<path d="{d["atPath"]}" fill="none" stroke="{INK}" stroke-width="{3.2 * scale:.1f}" stroke-linejoin="round" stroke-linecap="round"></path>')
    out.append(f'<path d="{d["atPath"]}" fill="none" stroke="{BLAZE_WHITE}" stroke-width="{1.6 * scale:.1f}" stroke-linejoin="round" stroke-linecap="round"></path>')
    # walked stretches in the taken-trail yellow, over the casing
    for p in d['walked']:
        if walked:
            out.append(f'<path d="{p}" fill="none" stroke="{BLAZE_YELLOW}" stroke-width="{4.2 * scale:.1f}" stroke-linecap="round" stroke-linejoin="round"></path>')
    # mile ticks every 500
    for m, t in d['tick'].items():
        px, py = t['p']; nx, ny = -t['nx'], -t['ny']
        L = 4 * scale
        out.append(f'<line x1="{px - nx * L:.1f}" y1="{py - ny * L:.1f}" x2="{px + nx * L:.1f}" y2="{py + ny * L:.1f}" stroke="{INK}" stroke-width="{1.2 * scale:.1f}"></line>')
        out.append(text(px + nx * (L + 4 * scale) - 2 * scale, py + ny * (L + 4 * scale) + 3.5 * scale,
                        f'mi {m}', 9 * scale, fill=STONE_600, anchor='end'))
    # places: hollow first, earned on top; cluster earned ones that overlap
    r = 5.0 * scale
    for m in hollow:
        x, y = d['atMile'][str(m)]
        out.append(diamond(x, y, r, False, scale))
    clusters = []
    for m in earned:
        x, y = d['atMile'][str(m)]
        for c in clusters:
            if abs(c['x'] - x) < cluster_px * scale and abs(c['y'] - y) < cluster_px * scale:
                c['n'] += 1; break
        else:
            clusters.append({'x': x, 'y': y, 'n': 1})
    for c in clusters:
        out.append(diamond(c['x'], c['y'], r, True, scale))
        if counts and c['n'] > 1:
            out.append(text(c['x'] + r * 1.6 + 3 * scale, c['y'] + 3.5 * scale, str(c['n']), 11 * scale, fill=INK, weight=500))
    if chosen is not None:
        x, y = d['atMile'][str(chosen)]
        out.append(chosen_ring(x, y, scale))
    for m, label, dx, dy, anchor in place_labels:
        x, y = d['atMile'][str(m)]
        out.append(text(x + dx * scale, y + dy * scale, label, 10 * scale, fill=INK, anchor=anchor, weight=500))
    # termini
    sx, sy = d['atMile']['0']; kx, ky = d['atMile']['2197.9']
    out.append(text(sx + 9 * scale, sy + 13 * scale, 'Springer Mtn · mi 0' if termini_miles else 'Springer Mtn', 10 * scale, fill=INK, weight=500))
    out.append(text(kx - 8 * scale, ky - 9 * scale, 'Katahdin · mi 2,198' if termini_miles else 'Katahdin', 10 * scale, fill=INK, anchor='end', weight=500))
    # scale bar + attribution, bottom-left / bottom-right
    sp = d['scalePx'] * scale
    bx, by = 14 * scale, 22 * scale
    out.append(f'<line x1="{bx:.1f}" y1="{by:.1f}" x2="{bx + sp:.1f}" y2="{by:.1f}" stroke="{INK}" stroke-width="{1.4 * scale:.1f}"></line>')
    out.append(f'<line x1="{bx:.1f}" y1="{by - 4 * scale:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{INK}" stroke-width="{1.4 * scale:.1f}"></line>')
    out.append(f'<line x1="{bx + sp:.1f}" y1="{by - 4 * scale:.1f}" x2="{bx + sp:.1f}" y2="{by:.1f}" stroke="{INK}" stroke-width="{1.4 * scale:.1f}"></line>')
    out.append(text(bx + sp / 2, by + 12 * scale, '200 mi', 9 * scale, fill=STONE_600, anchor='middle'))
    out.append(text(W - 10 * scale, H - 6 * scale, '© OpenStreetMap · US Census · Natural Earth', 7.5 * scale, fill=STONE_600, anchor='end'))
    out.append('</svg>')
    svg = ''.join(out)
    open(name, 'w').write(svg)
    print(name, len(svg))


OUT = '/tmp/claude-0/-home-claude/0c4726bb-b12c-5874-bfdf-d623f0ac990d/scratchpad/canvas/project/'
ALL_PLACES = [0, 200.1, 471.3, 703.1, 714.9, 720.3, 787.9, 830.5, 1026.5, 1106, 2045.9, 2080, 2197.9]

build(OUT + 'map-phone.svg', 'm2-line.json',
      earned=[0, 703.1, 713, 714.9, 714.9, 719.6, 787.9, 1026.5],
      hollow=[200.1, 380, 471.3, 830.5, 1106, 2045.9, 2080, 2197.9],
      walked=True, hide_states=('VA',),
      place_labels=[(714.9, 'McAfee Knob', 10, 17, 'start'), (1026.5, 'Harpers Ferry', 12, 14, 'start')],
      aria='Map of the eastern United States with the Appalachian Trail; your earned blazes marked along it as filled yellow diamonds, places still on your card as hollow diamonds, the stretches you walked in yellow')

build(OUT + 'map-where.svg', 'm2-where.json',
      earned=[0, 703.1, 713, 719.6, 787.9, 1026.5],
      hollow=[], walked=True, chosen=714.9, hide_states=('VA', 'WV'), counts=False,
      place_labels=[(714.9, 'McAfee Knob · mi 714.9', 30, -6, 'start'), (714.9, 'Virginia · here', 30, 8, 'start')],
      aria='Map of the Appalachian Trail with McAfee Knob, Virginia, ringed in orange as where this blaze will land')

build(OUT + 'map-welcome.svg', 'm2-welcome.json',
      earned=[], hollow=ALL_PLACES, walked=False, hide_states=('VA', 'WV', 'MD', 'NC'),
      termini_miles=True,
      place_labels=[(200.1, 'Kuwohi · mi 200', 10, 14, 'start'), (714.9, 'McAfee Knob · mi 715', 12, -9, 'start'),
                    (1026.5, 'Harpers Ferry · mi 1,027', 12, 15, 'start')],
      aria='Map of the Appalachian Trail from Springer Mountain to Katahdin with the Bucket List places marked along it and their mile markers')

build(OUT + 'map-poster.svg', 'm2-poster.json',
      earned=[0, 8, 703.1, 713, 714.9, 719.6, 720.3, 787.9, 830.5, 1026.5, 1030, 1106],
      hollow=[200.1, 471.3, 2045.9, 2080, 2197.9], walked=True, scale=1.15, hide_states=('VA',),
      place_labels=[(714.9, 'McAfee Knob', 10, 17, 'start')],
      aria='Map of the eastern United States with the Appalachian Trail and this hiker\'s earned blazes along it')
