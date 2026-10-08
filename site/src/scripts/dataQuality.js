// /data/quality/ in the browser: fetch the two files, draw what they say.
//
// CHECKED IN THE VISITOR'S BROWSER, from the same data base the app reads,
// rather than baked into the page when the site is built - the status page's
// argument (site/public/status/index.html): the hourly file is rewritten every
// hour and the site only at a tag, so a page built from the file would be
// stale by the next run. Each fetch is a plain GET of a public file; nothing
// about the visitor is sent.
//
// Everything this file decides is in src/lib/dataQuality.mjs and
// dataQualityHtml.mjs, where vitest can hold it. This is only the wiring:
// fetch, settle, draw, the chart's readout, and the Show menu and Chart
// buttons that choose what the chart draws.

import {
  FETCH_TIMEOUT_MS,
  LANES,
  NO_RANGE,
  buildPage,
  chartControls,
  chooseFromMenu,
  chooseFromRow,
  configFrom,
  initialChart,
  laneUrl,
  settleLane,
} from "../lib/dataQuality.mjs";
import {
  nearestPoint,
  renderBody,
  renderCard,
  renderChart,
  renderChartFigure,
  renderChartTitle,
  renderCharted,
} from "../lib/dataQualityHtml.mjs";

/** One lane's fetch: `read` with its JSON, `missing` on a 404, `failed` otherwise. */
async function fetchLane(url) {
  if (url === null) return { state: "unconfigured" };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    // no-store: the hourly file is replaced in place, and a cached copy of it
    // would be an earlier run presented as the latest.
    const response = await fetch(url, { cache: "no-store", signal: controller.signal });
    if (response.status === 404) return { state: "missing" };
    if (!response.ok) return { state: "failed", status: response.status };
    try {
      return { state: "read", json: await response.json() };
    } catch (error) {
      if (controller.signal.aborted) return { state: "failed", timedOut: true };
      // Not JSON at all: settleLane turns this into "not in the format this page reads".
      return { state: "read", json: undefined };
    }
  } catch {
    return { state: "failed", timedOut: controller.signal.aborted };
  } finally {
    clearTimeout(timer);
  }
}

/** The readout for point `i`: the value first, then when, then what was expected. */
function readout(chart, i) {
  const point = chart.points[i];
  const row = chart.rows[i];
  const value = point.value === null ? "No value" : chart.format.value(point.value);
  const range = point.min === null || point.max === null ? NO_RANGE : `Expected ${chart.format.range(point.min, point.max)}`;
  const lines = [value, row.whenFull, range];
  if (point.outside) lines.push(row.where);
  return lines;
}

function mountChart(holder, chart) {
  const box = holder.querySelector("[data-chart-svg]");
  const tip = holder.querySelector("[data-chart-tip]");
  const live = holder.querySelector("[data-chart-live]");
  let layout = null;
  let at = null;

  const hide = () => {
    at = null;
    tip.hidden = true;
    for (const mark of box.querySelectorAll("[data-cross], [data-focus]")) mark.setAttribute("visibility", "hidden");
  };

  const show = (i, { announce = false } = {}) => {
    at = i;
    const x = layout.xs[i];
    const y = layout.ys[i];
    const cross = box.querySelector("[data-cross]");
    cross.setAttribute("x1", x);
    cross.setAttribute("x2", x);
    cross.setAttribute("visibility", "visible");
    const focus = box.querySelector("[data-focus]");
    if (y === null) focus.setAttribute("visibility", "hidden");
    else {
      focus.setAttribute("cx", x);
      focus.setAttribute("cy", y);
      focus.setAttribute("visibility", "visible");
    }
    const lines = readout(chart, i);
    tip.replaceChildren(
      ...lines.map((line, n) => {
        const span = document.createElement(n === 0 ? "strong" : "span");
        span.textContent = line;
        return span;
      }),
    );
    tip.hidden = false;
    const half = tip.offsetWidth / 2;
    tip.style.left = `${Math.min(layout.width - half, Math.max(half, x))}px`;
    tip.style.top = `${y ?? layout.plot.top + layout.plot.height / 2}px`;
    if (announce) live.textContent = lines.join(". ");
  };

  const draw = () => {
    const width = Math.floor(box.clientWidth);
    if (width < 1 || (layout && layout.width === width)) return;
    const drawn = renderChart(chart, width);
    box.innerHTML = drawn.markup;
    layout = drawn.layout;
    const hit = box.querySelector("[data-hit]");
    hit.addEventListener("pointermove", (event) => {
      const left = box.getBoundingClientRect().left;
      show(nearestPoint(layout.xs, event.clientX - left));
    });
    hit.addEventListener("pointerleave", () => {
      if (document.activeElement !== holder) hide();
    });
    if (at !== null) show(at);
  };

  holder.addEventListener("focus", () => show(at ?? chart.points.length - 1, { announce: true }));
  holder.addEventListener("blur", hide);
  holder.addEventListener("keydown", (event) => {
    const last = chart.points.length - 1;
    const moves = {
      ArrowLeft: () => Math.max(0, (at ?? last) - 1),
      ArrowRight: () => Math.min(last, (at ?? last) + 1),
      Home: () => 0,
      End: () => last,
    };
    if (event.key === "Escape") return hide();
    if (!(event.key in moves)) return;
    event.preventDefault();
    show(moves[event.key](), { announce: true });
  });

  draw();
  // Returned so a chart replaced by another series stops redrawing into a
  // box that is no longer on the page.
  if ("ResizeObserver" in window) {
    const observer = new ResizeObserver(() => requestAnimationFrame(draw));
    observer.observe(box);
    return () => observer.disconnect();
  }
  window.addEventListener("resize", draw);
  return () => window.removeEventListener("resize", draw);
}

/** Smoothly unless the reader asked for less motion; site.css's `scroll-behavior` says the same. */
const motion = () => (window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");

/** The listeners of the last draw's chart, so the next draw can take them off. */
let wired = null;

/**
 * The Show menu and the Chart buttons, kept in step through one state
 * (dataQuality.mjs's chartControls decides what each shows; this applies it).
 * A Chart button also takes the reader to the chart, and the chart's "Back to
 * the row" link takes them back to the button they pressed.
 */
function wireChart(body, sections) {
  // The body element outlives each draw, so its click listener from a
  // previous draw is taken off before this one's goes on.
  wired?.abort();
  wired = new AbortController();
  const { signal } = wired;
  const card = body.querySelector("[data-chart-figure]")?.closest("section");
  if (!card) return;
  const slot = card.querySelector("[data-chart-figure]");
  const select = card.querySelector("[data-chart-select]");
  const line = card.querySelector("[data-charted]");
  let state = initialChart(sections);
  let unmount = mountChart(slot.querySelector("[data-chart]"), sections.chart);

  const apply = (next) => {
    const changed = next.key !== state.key;
    state = next;
    const shown = chartControls(sections, state);
    if (changed && shown.chart) {
      card.querySelector("[data-chart-title]").innerHTML = renderChartTitle(shown.chart);
      const tableOpen = slot.querySelector("details")?.open ?? false;
      unmount();
      slot.innerHTML = renderChartFigure(shown.chart, { tableOpen });
      unmount = mountChart(slot.querySelector("[data-chart]"), shown.chart);
    }
    if (select) select.value = shown.selected;
    for (const button of body.querySelectorAll("[data-chart-key]")) {
      button.setAttribute("aria-pressed", String(shown.pressed.includes(button.dataset.row)));
    }
    line.innerHTML = renderCharted(shown.charted);
    line.hidden = shown.charted === null;
  };

  select?.addEventListener("change", () => apply(chooseFromMenu(select.value)), { signal });

  body.addEventListener("click", (event) => {
    const button = event.target.closest("[data-chart-key]");
    if (button) {
      const next = chooseFromRow(sections, button.dataset.row);
      if (!next) return;
      apply(next);
      // To the chart, and focus on its title, so a screen reader hears what is
      // drawn now and the next Tab is the way back.
      card.scrollIntoView({ behavior: motion(), block: "start" });
      card.querySelector("[data-chart-title]").focus({ preventScroll: true });
      return;
    }
    const back = event.target.closest("[data-back]");
    if (!back || state.origin === null) return;
    event.preventDefault();
    const row = document.getElementById(state.origin);
    if (!row) return;
    // The row may be a warning inside a fold the reader has since closed.
    const fold = row.closest("details");
    if (fold) fold.open = true;
    row.scrollIntoView({ behavior: motion(), block: "center" });
    // The pressed button the reader can see: a mart's row holds two, one per width.
    const pressed = [...row.querySelectorAll("[data-chart-key]")].find((candidate) => candidate.offsetParent !== null);
    (pressed ?? row).focus({ preventScroll: true });
  }, { signal });
}

function draw(root, config, lanes) {
  const view = buildPage({ config, monthly: lanes.monthly, hourly: lanes.hourly, now: new Date() });
  for (const card of view.cards) {
    const slot = root.querySelector(`[data-card="${card.lane}"]`);
    if (slot) slot.innerHTML = renderCard(card);
  }
  const body = root.querySelector('[data-slot="body"]');
  body.innerHTML = renderBody(view);
  body.setAttribute("aria-busy", String(view.loading));
  const madeFrom = root.querySelector('[data-slot="made-from"]');
  if (madeFrom) {
    madeFrom.textContent = view.colophon ?? "";
    madeFrom.hidden = view.colophon === null;
  }
  if (view.sections?.chart) wireChart(body, view.sections);
}

/** Read the two files and draw the page into `root`, the element carrying `data-base` and `data-release`. */
export async function start(root) {
  if (!root) return;
  const config = configFrom({ base: root.dataset.base, release: root.dataset.release });
  const lanes = { monthly: { state: "loading" }, hourly: { state: "loading" } };
  if (!config.configured) {
    lanes.monthly = { state: "unconfigured" };
    lanes.hourly = { state: "unconfigured" };
    return draw(root, config, lanes);
  }
  draw(root, config, lanes);
  await Promise.all(
    LANES.map(async (lane) => {
      lanes[lane] = settleLane(await fetchLane(laneUrl(config, lane)), lane);
      // Why a file was refused goes to the console, never the page: the page
      // says only that it is not in the format it reads.
      if (lanes[lane].state === "invalid") console.warn(`data_quality.json (${lane}) refused: ${lanes[lane].why}`);
    }),
  );
  draw(root, config, lanes);
}
