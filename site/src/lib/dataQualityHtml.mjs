// The markup /data/quality/ draws from buildPage()'s view (dataQuality.mjs),
// as strings: the site has no DOM library and its vitest suite no jsdom, so a
// string is what both the browser (src/scripts/dataQuality.js sets it as
// innerHTML) and a test can read.
//
// EVERY VALUE IS ESCAPED BY CONSTRUCTION. `html` is a tagged template whose
// interpolations are escaped unless they are themselves `html` output, so a
// table name from the file cannot become markup by somebody forgetting to
// escape it. Names come from a build, not a person, but the page is on the
// app's origin, where a signed-in hiker's session is kept (pipeline/ELT.md
// decision 93), so it is held to the rule anyway.
//
// The chart is drawn at the pixel width it is given, not scaled from a fixed
// viewBox: mock B's 960-wide drawing shrunk onto a 390 px phone set its 12 px
// labels at under 5 px. src/scripts/dataQuality.js measures the box and
// redraws when it changes size.

import { formatTickLabel } from "./dataQuality.mjs";

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

/** Text made safe for HTML, in an element or an attribute. */
export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ESCAPES[char]);
}

class Markup {
  constructor(text) {
    this.text = text;
  }

  toString() {
    return this.text;
  }
}

function piece(value) {
  if (value instanceof Markup) return value.text;
  if (Array.isArray(value)) return value.map(piece).join("");
  if (value === null || value === undefined || value === false) return "";
  return escapeHtml(value);
}

/** A template whose interpolations are escaped unless they are markup already. */
export function html(strings, ...values) {
  return new Markup(strings.reduce((out, text, i) => out + text + (i < values.length ? piece(values[i]) : ""), ""));
}

/**
 * A table, column or mart name, with a line break offered after each
 * underscore, so "points_of_interest" wraps as "points_of_ / interest" in a
 * phone's narrow column rather than mid-word. Escaped first, so the only
 * markup added is the `<wbr>`.
 */
export function name(text) {
  return new Markup(`<code>${escapeHtml(text).replace(/_(?=[^_])/g, "_<wbr>")}</code>`);
}

/** Text with names in it - strings, and `{code}` for a table, column or mart. */
export function segments(parts) {
  return parts.map((part) => (typeof part === "string" ? html`${part}` : name(part.code)));
}

const ICONS = { ok: "dq-i-ok", warn: "dq-i-warn", bad: "dq-i-bad", neutral: "dq-i-wait" };

/** A tone's icon: a different shape for each, so no state is told by colour alone. */
export function icon(tone) {
  return html`<svg class="dq-icon" aria-hidden="true" focusable="false"><use href="#${ICONS[tone]}"></use></svg>`;
}

export function pill({ tone, text }) {
  return html`<span class="dq-pill dq-pill--${tone}">${icon(tone)}${text}</span>`;
}

const pills = (list) => html`<p class="dq-pills">${list.map(pill)}</p>`;

/** The inside of one build's card. */
export function renderCard(card) {
  return html`<h2 class="dq-run__title">${card.title}</h2>
<p class="dq-run__meta">${card.meta}</p>
${card.detail ? html`<p class="dq-run__detail">${card.detail}</p>` : ""}
${card.pills.length ? pills(card.pills) : ""}
${
  card.learning
    ? html`<div class="dq-run__learning">${pill({ tone: "neutral", text: card.learning.text })}<p>${card.learning.detail}</p></div>`
    : ""
}`.text;
}

function renderNotice(notice) {
  return html`<section class="dq-panel dq-notice" aria-labelledby="dq-notice-title">
<h2 id="dq-notice-title">${notice.title}</h2>
<p>${notice.body}</p>
</section>`;
}

function renderTile(tile) {
  return html`<article class="dq-panel dq-tile">
<h3 class="dq-tile__kind">${tile.label}</h3>
${pills(tile.pills)}
<p class="dq-tile__figure">${tile.figure.passed}<small>${tile.figure.checks === null ? tile.caption : `of ${tile.figure.checks} ${tile.caption}`}</small></p>
<p class="dq-tile__note">${segments(tile.note)}</p>
${tile.learning ? html`<p class="dq-tile__learning">${tile.learning}</p>` : ""}
</article>`;
}

function renderItem(item) {
  return html`<li class="dq-panel dq-item dq-item--${item.tone}">
<span class="dq-item__stripe" aria-hidden="true"></span>
<div class="dq-item__what">
<p class="dq-item__head">${item.kind} · ${name(item.table)}${item.column ? html` · ${name(item.column)}` : ""}</p>
<p class="dq-item__sentence">${item.sentence}</p>
</div>
<div class="dq-item__when">
${pill({ tone: item.tone, text: item.status })}
<p>${item.lane}${item.since ? ` · ${item.since}` : ""}</p>
</div>
</li>`;
}

function renderMarts(marts) {
  if (marts.length === 0) return html`<p class="dq-panel dq-quiet">No mart was checked in these builds.</p>`;
  return html`<div class="dq-panel dq-table-wrap">
<table class="dq-table" aria-labelledby="dq-marts-title">
<thead><tr><th scope="col">Mart</th><th scope="col" class="dq-col-lane">Lane</th><th scope="col" class="dq-num">Checks</th><th scope="col">Result</th></tr></thead>
<tbody>
${marts.map(
  (row) => html`<tr><td>${name(row.mart)}<span class="dq-lane-tag">${row.lane}</span></td><td class="dq-col-lane">${row.lane}</td><td class="dq-num">${row.checks}</td><td><p class="dq-pills">${row.pills.map(pill)}</p></td></tr>
`,
)}
</tbody>
</table>
</div>`;
}

function renderChartSection(chart) {
  return html`<section class="dq-section dq-panel dq-chart-card" aria-labelledby="dq-chart-title">
<h2 id="dq-chart-title">${segments(chart.title)}</h2>
<figure class="dq-figure">
<div class="dq-key" aria-hidden="true">
<span><i class="dq-key__line"></i>${chart.format.label} at each point</span>
<span><i class="dq-key__band"></i>Expected range</span>
<span><svg class="dq-key__out" viewBox="0 0 16 16"><path d="M8 1.5 15 14H1z"></path></svg>Outside it</span>
</div>
<div class="dq-chart" data-chart tabindex="0" role="group" aria-label="The chart, point by point: use the left and right arrow keys">
<div class="dq-chart__svg" data-chart-svg></div>
<div class="dq-tip" data-chart-tip hidden></div>
<p class="dq-sr" aria-live="polite" data-chart-live></p>
</div>
<figcaption class="dq-figcaption">${chart.summary} ${chart.caption}</figcaption>
<details class="dq-details">
<summary>The numbers behind the chart</summary>
<div class="dq-table-wrap">
<table class="dq-table">
<thead><tr><th scope="col">When (UTC)</th><th scope="col" class="dq-num">${chart.format.label}</th><th scope="col">Expected range</th></tr></thead>
<tbody>
${chart.rows.map(
  (row) => html`<tr><td class="dq-when">${row.when}</td><td class="dq-num">${row.value}</td><td>${row.expected}</td></tr>
`,
)}
</tbody>
</table>
</div>
</details>
</figure>
</section>`;
}

/** Everything under the two build cards: a notice, or the four sections. */
export function renderBody(view) {
  if (view.notice) return renderNotice(view.notice).text;
  if (!view.sections) return "";
  const s = view.sections;
  return html`<section class="dq-section" aria-labelledby="dq-kinds-title">
<h2 id="dq-kinds-title">The five kinds of check</h2>
<p class="dq-scope">${s.scope}</p>
<div class="dq-tiles">${s.tiles.map(renderTile)}</div>
</section>
<section class="dq-section" aria-labelledby="dq-look-title">
<h2 id="dq-look-title">Needs a look</h2>
${
  s.items.length
    ? html`<ul class="dq-items">${s.items.map(renderItem)}</ul>`
    : html`<p class="dq-panel dq-quiet">${icon("ok")}<span>${s.quiet}</span></p>`
}
</section>
${s.chart ? renderChartSection(s.chart) : ""}
<section class="dq-section" aria-labelledby="dq-marts-title">
<h2 id="dq-marts-title">By mart</h2>
${renderMarts(s.marts)}
</section>`.text;
}

// ---------------------------------------------------------------- the chart

/** Steps a duration axis snaps to, in seconds: a tick at 6 h, never at 6.94 h. */
const DURATION_STEPS = [60, 300, 600, 900, 1800, 3600, 7200, 10800, 21600, 43200, 86400, 172800, 604800];

/**
 * Round tick values covering `lo` to `hi`, about `count` of them: 4,118 to
 * 5,319 rows gives 4,000, 4,500, 5,000 and 5,500. Durations snap to minutes,
 * hours and days rather than to powers of ten.
 */
export function niceTicks(lo, hi, count = 5, { duration = false } = {}) {
  let [a, b] = [lo, hi];
  if (!(b > a)) {
    const pad = Math.abs(a) * 0.1 || 1;
    a -= pad;
    b += pad;
  }
  const rough = (b - a) / Math.max(1, count - 1);
  let step;
  if (duration) step = DURATION_STEPS.find((s) => s >= rough) ?? Math.ceil(rough / 604800) * 604800;
  else {
    const magnitude = 10 ** Math.floor(Math.log10(rough));
    step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= rough);
  }
  const start = Math.floor(a / step) * step;
  const end = Math.ceil(b / step) * step;
  const ticks = [];
  for (let v = start; v <= end + step / 2; v += step) ticks.push(Number(v.toPrecision(12)));
  return ticks;
}

const CHAR_PX = 6.8; // Public Sans at 12 px, digits and lower case, measured by eye from a render
const TOP = 14;
const BOTTOM = 30;
const RIGHT = 16;

/**
 * Where everything in the chart goes at `width` CSS pixels: each point's x and
 * y (y null where a point has no value), the plot box, the ticks. The browser
 * uses the same numbers to put its crosshair on the nearest point.
 */
export function chartLayout(chart, width) {
  const height = width < 560 ? 220 : 280;
  const { floor } = chart.format;
  const values = chart.points.flatMap((p) => [p.value, p.min, p.max]).filter((v) => v !== null);
  let lo = values.length ? Math.min(...values) : 0;
  let hi = values.length ? Math.max(...values) : 1;
  // Counts, rates and durations cannot go below zero, so a band Elementary's
  // arithmetic put there is drawn from zero (dataQuality.mjs, METRICS).
  if (floor !== null) lo = Math.max(lo, floor);
  const ticks = niceTicks(lo, hi, height < 250 ? 4 : 5, { duration: chart.format.duration });
  lo = ticks[0];
  hi = ticks[ticks.length - 1];
  const labels = chart.format.ticks(ticks);
  const left = Math.ceil(Math.max(...labels.map((label) => label.length)) * CHAR_PX) + 14;
  const plot = { left, top: TOP, width: Math.max(40, width - left - RIGHT), height: height - TOP - BOTTOM };
  const n = chart.points.length;
  const x = (i) => (n === 1 ? plot.left + plot.width / 2 : plot.left + (i * plot.width) / (n - 1));
  const y = (v) => plot.top + ((hi - Math.max(v, lo)) * plot.height) / (hi - lo);
  return {
    width,
    height,
    plot,
    ticks: ticks.map((value, i) => ({ value, label: labels[i], y: y(value) })),
    xs: chart.points.map((_, i) => x(i)),
    ys: chart.points.map((p) => (p.value === null ? null : y(p.value))),
    band: chart.points.map((p) => (p.min === null || p.max === null ? null : [y(p.max), y(p.min)])),
  };
}

/** Runs of consecutive indices for which `keep(i)` holds. */
function runs(n, keep) {
  const out = [];
  let current = [];
  for (let i = 0; i < n; i += 1) {
    if (keep(i)) current.push(i);
    else if (current.length) {
      out.push(current);
      current = [];
    }
  }
  if (current.length) out.push(current);
  return out;
}

/** Which points are offered an x-axis label: evenly spaced, always the first and the last. */
function labelled(n, room) {
  const most = Math.max(2, Math.floor(room / 76));
  if (n <= most) return [...Array(n).keys()];
  const step = Math.ceil((n - 1) / (most - 1));
  const picked = [];
  for (let i = 0; i < n - 1; i += step) picked.push(i);
  if (n - 1 - picked[picked.length - 1] < step / 2) picked.pop();
  picked.push(n - 1);
  return picked;
}

const LABEL_GAP = 10;

/**
 * The x-axis labels that fit: each placed under its point, pulled inside the
 * frame at either end, and dropped when it would come within LABEL_GAP of a
 * neighbour - the first and the last are always kept. Pulling the last label
 * in is what can bring it onto the one before it ("Sep 2026Oct 2026" in the
 * first render at 1280 px), so that is checked after placing, not before.
 */
export function axisLabels(chart, xs, width, room) {
  const placed = labelled(xs.length, room).map((i) => {
    const text = formatTickLabel(chart.points[i].at, chart.lane);
    const w = text.length * CHAR_PX;
    if (xs[i] - w / 2 < 2) {
      const x = Math.max(2, xs[i] - 4);
      return { i, text, anchor: "start", x, start: x, end: x + w };
    }
    if (xs[i] + w / 2 > width - 2) {
      const x = Math.min(width - 2, xs[i] + 4);
      return { i, text, anchor: "end", x, start: x - w, end: x };
    }
    return { i, text, anchor: "middle", x: xs[i], start: xs[i] - w / 2, end: xs[i] + w / 2 };
  });
  const last = placed[placed.length - 1];
  const kept = [];
  for (const label of placed) {
    const before = kept[kept.length - 1];
    if (label !== last && before && label.start < before.end + LABEL_GAP) continue;
    if (label !== last && last && label.end + LABEL_GAP > last.start) continue;
    kept.push(label);
  }
  return kept;
}

const r1 = (v) => Math.round(v * 10) / 10;

/** The chart's SVG at `width` CSS pixels, and the layout it was drawn from. */
export function renderChart(chart, width) {
  const layout = chartLayout(chart, width);
  const { plot, xs, ys, band } = layout;
  const n = chart.points.length;
  const parts = [];

  for (const tick of layout.ticks) {
    parts.push(
      html`<line class="dq-chart__grid" x1="${plot.left}" x2="${plot.left + plot.width}" y1="${r1(tick.y)}" y2="${r1(tick.y)}"></line><text class="dq-chart__tick" x="${plot.left - 8}" y="${r1(tick.y + 4)}" text-anchor="end">${tick.label}</text>`,
    );
  }

  for (const run of runs(n, (i) => band[i] !== null)) {
    if (run.length === 1) {
      const [i] = run;
      const [top, bottom] = band[i];
      parts.push(
        html`<rect class="dq-chart__band" x="${r1(xs[i] - 6)}" y="${r1(top)}" width="12" height="${r1(Math.max(1, bottom - top))}" rx="3"></rect>`,
      );
      continue;
    }
    const upper = run.map((i) => `${r1(xs[i])},${r1(band[i][0])}`);
    const lower = run
      .slice()
      .reverse()
      .map((i) => `${r1(xs[i])},${r1(band[i][1])}`);
    parts.push(html`<path class="dq-chart__band" d="M${upper.join("L")}L${lower.join("L")}Z"></path>`);
  }

  for (const run of runs(n, (i) => ys[i] !== null)) {
    if (run.length < 2) continue;
    parts.push(html`<path class="dq-chart__line" d="M${run.map((i) => `${r1(xs[i])},${r1(ys[i])}`).join("L")}"></path>`);
  }

  const spacing = n > 1 ? plot.width / (n - 1) : plot.width;
  const lastDrawn = ys.findLastIndex((v) => v !== null);
  chart.points.forEach((point, i) => {
    if (ys[i] === null) return;
    if (point.outside) {
      const [px, py] = [r1(xs[i]), r1(ys[i])];
      parts.push(
        html`<path class="dq-chart__out" d="M${px},${r1(py - 7.5)}L${r1(px + 7)},${r1(py + 5)}L${r1(px - 7)},${r1(py + 5)}Z"></path>`,
      );
    } else if (spacing >= 10 || i === lastDrawn) {
      parts.push(html`<circle class="dq-chart__dot" cx="${r1(xs[i])}" cy="${r1(ys[i])}" r="4"></circle>`);
    }
  });

  // The one direct label: the latest point outside the range, named in words.
  const flagged = chart.points.findLastIndex((point, i) => point.outside && ys[i] !== null);
  if (flagged !== -1) {
    const point = chart.points[flagged];
    const text = `${chart.format.value(point.value)}, ${point.outside} the range`;
    const rightHalf = xs[flagged] > plot.left + plot.width / 2;
    const ty = Math.min(plot.top + plot.height - 4, Math.max(plot.top + 12, ys[flagged] + 4));
    parts.push(
      html`<text class="dq-chart__label" x="${r1(xs[flagged] + (rightHalf ? -14 : 14))}" y="${r1(ty)}" text-anchor="${rightHalf ? "end" : "start"}">${text}</text>`,
    );
  }

  for (const label of axisLabels(chart, xs, width, plot.width)) {
    parts.push(
      html`<text class="dq-chart__tick" x="${r1(label.x)}" y="${layout.height - 8}" text-anchor="${label.anchor}">${label.text}</text>`,
    );
  }

  parts.push(
    html`<line class="dq-chart__cross" data-cross x1="0" x2="0" y1="${plot.top}" y2="${plot.top + plot.height}" visibility="hidden"></line><circle class="dq-chart__focus" data-focus r="7" cx="0" cy="0" visibility="hidden"></circle><rect class="dq-chart__hit" data-hit x="${plot.left - 12}" y="0" width="${plot.width + 24}" height="${layout.height}" fill="transparent"></rect>`,
  );

  const markup = html`<svg width="${width}" height="${layout.height}" viewBox="0 0 ${width} ${layout.height}" role="img" aria-label="${chart.summary}">${parts}</svg>`;
  return { markup: markup.text, layout };
}

/** The index of the point nearest `x`, for the crosshair. */
export function nearestPoint(xs, x) {
  let best = 0;
  for (let i = 1; i < xs.length; i += 1) if (Math.abs(xs[i] - x) < Math.abs(xs[best] - x)) best = i;
  return best;
}
