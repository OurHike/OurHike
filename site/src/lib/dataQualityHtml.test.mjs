// /data/quality/'s markup, from the same invented files dataQuality.test.mjs
// reads: that a name from a file is escaped wherever it lands, that the page
// prints no name the file does not hold, that every state's card and body
// carry their words, and the chart's geometry - its ticks, its band, the
// triangle and label on a point outside the band, and axis labels that never
// collide (the first render at 1280 px put "Sep 2026" and "Oct 2026" a pixel
// apart). And that every class the markup uses has a rule in site.css, the
// org pages' own guard (siteCss.test.mjs) applied to this page.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { buildPage, configFrom, formatCount, settleLane } from "./dataQuality.mjs";
import {
  axisLabels,
  chartLayout,
  icon,
  name,
  nearestPoint,
  niceTicks,
  renderBody,
  renderCard,
  renderChart,
  renderChartFigure,
  renderCharted,
} from "./dataQualityHtml.mjs";
import * as examples from "./dataQualityExamples.mjs";

const read = (path) => readFileSync(fileURLToPath(new URL(path, import.meta.url)), "utf8");
const NOW = new Date("2026-10-08T01:00:00Z");
const CONFIG = configFrom({ base: "https://data.example.invalid", release: "2026-10-03-2" });
const lane = (json, which) => settleLane({ state: "read", json }, which);
const MISSING = { state: "missing" };
const view = (monthly, hourly) => buildPage({ config: CONFIG, monthly, hourly, now: NOW });
const lookingView = () =>
  view(lane(examples.monthlyWithWarnings(), "monthly"), lane(examples.hourlyWithWarning(), "hourly"));
const manyView = () =>
  view(lane(examples.monthlyManyProblems(), "monthly"), lane(examples.hourlyManyProblems(), "hourly"));
const codes = (markup) => [...markup.matchAll(/<code>(.*?)<\/code>/g)].map((m) => m[1].replaceAll("<wbr>", ""));

describe("names from a file", () => {
  it("are escaped wherever the page prints them", () => {
    const hostile = '<img src=x onerror="alert(1)">';
    const file = examples.monthlyWithWarnings();
    // A status the page does not know is printed in the file's own word, so
    // it reaches the markup through the template rather than through name().
    file.needs_a_look = file.needs_a_look.map((item) => ({ ...item, table: hostile, column: hostile, status: hostile }));
    file.series = file.series.map((series) => ({ ...series, table: hostile }));
    file.by_mart = [{ ...file.by_mart[0], mart: `"><script>alert(1)</script>` }];
    const page = view(lane(file, "monthly"), MISSING);
    const body = renderBody(page);
    expect(body).not.toContain("<img");
    expect(body).not.toContain("<script");
    expect(body).toContain("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;");
    const { markup } = renderChart(page.sections.chart, 900);
    expect(markup).not.toContain("<img");
  });

  it("are escaped in the Chart buttons, the Show menu and the line naming where a chart came from", () => {
    const hostile = '"><img src=x onerror="alert(1)">';
    const file = examples.monthlyManyProblems();
    file.needs_a_look = file.needs_a_look.map((item) => ({ ...item, table: `${item.table}${hostile}` }));
    file.series = file.series.map((series) => ({ ...series, table: `${series.table}${hostile}` }));
    file.by_mart = file.by_mart.map((mart) => ({ ...mart, mart: `${mart.mart}${hostile}` }));
    const page = view(lane(file, "monthly"), MISSING);
    const body = renderBody(page);
    expect(body).toContain('data-chart-key="');
    expect(body).toContain("<optgroup");
    expect(body).not.toContain("<img");
    const [button] = page.sections.buttons;
    expect(renderCharted({ ...button, row: `${button.row}${hostile}` })).not.toContain("<img");
  });

  it("break after an underscore and nowhere else, so a phone column wraps a name between its words", () => {
    expect(name("points_of_interest").text).toBe("<code>points_<wbr>of_<wbr>interest</code>");
    expect(name("preview_fixture__trails").text).toBe("<code>preview_<wbr>fixture__<wbr>trails</code>");
    expect(name("a<b").text).toBe("<code>a&lt;b</code>");
  });

  it("are the only names the page prints", () => {
    const monthly = examples.monthlyWithWarnings();
    const hourly = examples.hourlyWithWarning();
    const filed = new Set(
      [monthly, hourly].flatMap((file) => [
        ...file.needs_a_look.flatMap((item) => [item.table, item.column]),
        ...file.series.map((series) => series.table),
        ...file.by_mart.map((mart) => mart.mart),
      ]),
    );
    const printed = codes(renderBody(lookingView()));
    expect(printed.length).toBeGreaterThan(0);
    expect(printed.filter((printedName) => !filed.has(printedName))).toEqual([]);
  });
});

describe("cards and bodies", () => {
  it("draws each state's card in its words", () => {
    const cases = [
      [{ state: "loading" }, "Reading…"],
      [MISSING, "Not published yet"],
      [{ state: "failed", status: 503 }, "The data host answered 503."],
      [{ state: "invalid", why: "format is not ourhike-data-quality/1" }, "not in the format this page reads"],
    ];
    for (const [state, words] of cases) {
      const [card] = view(state, MISSING).cards;
      expect(renderCard(card)).toContain(words);
    }
  });

  it("gives a card's pills an icon of their own shape", () => {
    const [card] = lookingView().cards;
    const markup = renderCard(card);
    expect(markup).toContain("#dq-i-ok");
    expect(markup).toContain("#dq-i-warn");
    expect(new Set(["ok", "warn", "bad", "neutral"].map((tone) => icon(tone).text)).size).toBe(4);
  });

  it("defines every icon the markup uses, on the page itself", () => {
    const page = read("../pages/data/quality/index.astro");
    for (const id of ["dq-i-ok", "dq-i-warn", "dq-i-bad", "dq-i-wait"]) expect(page).toContain(`id="${id}"`);
  });

  it("puts a notice where there is nothing to count, and the four sections where there is", () => {
    expect(renderBody(view(MISSING, MISSING))).toContain("Nothing is published yet");
    const body = renderBody(lookingView());
    for (const heading of ["The five kinds of check", "Needs a look", "By mart"]) expect(body).toContain(heading);
    expect(body).toContain("dq-chart-card");
    expect(renderBody(view(lane(examples.monthlyAllGreen(), "monthly"), MISSING))).not.toContain("dq-chart-card");
  });

  it("gives the chart a table of every point it draws", () => {
    const body = renderBody(lookingView());
    const table = body.slice(body.indexOf("The numbers behind the chart"));
    const points = examples.monthlyWithWarnings().series[0].points.length;
    expect([...table.slice(0, table.indexOf("</table>")).matchAll(/<tr><td class="dq-when">/g)]).toHaveLength(points);
  });

  it("keeps the table of numbers open across a change of series, when the reader had opened it", () => {
    const { chart } = lookingView().sections;
    expect(renderChartFigure(chart)).toContain('<details class="dq-details">');
    expect(renderChartFigure(chart, { tableOpen: true })).toContain('<details class="dq-details" open>');
  });
});

describe("Needs a look, the Show menu and the Chart buttons, as markup", () => {
  it("puts every failed and unrunnable entry before the first fold, and only warnings inside one", () => {
    const body = renderBody(manyView());
    const look = body.slice(body.indexOf('id="dq-look-title"'), body.indexOf('id="dq-chart"'));
    const firstFold = look.indexOf("<details");
    const statuses = (markup) => [...markup.matchAll(/dq-pill--\w+">.*?<\/svg>([^<]+)<\/span>/g)].map((m) => m[1]);
    expect(statuses(look.slice(0, firstFold))).toEqual([...Array(4).fill("Failed"), ...Array(4).fill("Could not run")]);
    expect(new Set(statuses(look.slice(firstFold)))).toEqual(new Set(["Warned"]));
    expect(look.match(/<details class="dq-panel dq-fold"/g)).toHaveLength(4);
    expect(look).not.toMatch(/<details class="dq-panel dq-fold"[^>]* open/);
  });

  it("draws a Chart button on each row with a history and two per mart, the first chart's row pressed as the page opens", () => {
    const page = manyView();
    const body = renderBody(page);
    expect(body.match(/<button type="button" class="dq-chart-btn"/g)).toHaveLength(30 + 11);
    expect(body.match(/class="dq-chart-btn dq-chart-btn--inline"/g)).toHaveLength(11);
    const pressed = [...body.matchAll(/data-row="([^"]+)" aria-pressed="true"/g)].map((m) => m[1]);
    expect(pressed).toEqual([page.sections.opening]);
    expect(body).toContain(
      `<li class="dq-panel dq-item dq-item--bad" id="${page.sections.opening}">`,
    );
    expect(body).toContain('aria-label="Chart null rate of trail_status in trail_lines, Monthly">');
    expect(body).toContain(
      `<p class="dq-charted" data-charted>Charted from Needs a look · <code>trail_<wbr>lines</code> · <code>trail_<wbr>status</code> · <a href="#${page.sections.opening}" data-back>Back to the row</a></p>`,
    );
  });

  it("opens a fold of 3 warnings and keeps a fold of 4 closed", () => {
    const monthly = examples.monthlyManyProblems();
    const kept = { schema: 3, anomalies: 4 };
    const seen = { schema: 0, anomalies: 0 };
    monthly.needs_a_look = monthly.needs_a_look.filter((entry) => {
      if (entry.status !== "warn" || !(entry.kind in kept)) return true;
      seen[entry.kind] += 1;
      return seen[entry.kind] <= kept[entry.kind];
    });
    const body = renderBody(view(lane(monthly, "monthly"), MISSING));
    expect(body).toContain('<details class="dq-panel dq-fold" data-fold="schema" open>');
    expect(body).toContain('<details class="dq-panel dq-fold" data-fold="anomalies">');
    expect(renderBody(lookingView()).match(/<details class="dq-panel dq-fold" data-fold="\w+" open>/g)).toHaveLength(4);
  });

  it("draws the Show menu as a native select in its two groups, the chart's series selected", () => {
    const page = manyView();
    const body = renderBody(page);
    expect(body).toContain('<label class="dq-show__label" for="dq-show">Show</label>');
    expect(body.match(/<optgroup label="([^"]+)">/g)).toEqual(['<optgroup label="Needs a look">', '<optgroup label="Every mart">']);
    const selected = [...body.matchAll(/<option value="([^"]*)" selected>/g)].map((m) => m[1].replaceAll("&quot;", '"'));
    expect(selected).toEqual([page.sections.chart.key]);
    expect(body.match(/<option /g)).toHaveLength(38);
  });

  it("leaves the menu out when the files hold one series, and the Chart column out when no mart has one", () => {
    const body = renderBody(lookingView());
    expect(body).not.toContain("<select");
    expect(body).not.toContain("dq-col-chart");
  });

  it("names where a chart came from, with the way back to its row", () => {
    expect(renderCharted(null)).toBe("");
    expect(renderCharted({ from: "By mart", table: "trail_network", column: null, row: "dq-mart-2" })).toBe(
      'Charted from By mart · <code>trail_<wbr>network</code> · <a href="#dq-mart-2" data-back>Back to the row</a>',
    );
  });
});

describe("the chart", () => {
  const chart = () => lookingView().sections.chart;

  it("puts its ticks on round numbers, and a duration's on round hours", () => {
    expect(niceTicks(4118, 5319, 5)).toEqual([4000, 4500, 5000, 5500]);
    expect(niceTicks(0, 1, 5)).toEqual([0, 0.25, 0.5, 0.75, 1]);
    const hours = niceTicks(600, 93_600, 5, { duration: true });
    expect(hours.every((tick) => tick % 3600 === 0)).toBe(true);
    expect(hours[0]).toBeLessThanOrEqual(600);
    expect(hours.at(-1)).toBeGreaterThanOrEqual(93_600);
  });

  it("is shorter on a phone, and keeps every point inside its plot", () => {
    for (const [width, height] of [
      [320, 220],
      [900, 280],
    ]) {
      const layout = chartLayout(chart(), width);
      expect(layout.height).toBe(height);
      for (const x of layout.xs) {
        expect(x).toBeGreaterThanOrEqual(layout.plot.left);
        expect(x).toBeLessThanOrEqual(layout.plot.left + layout.plot.width);
      }
      expect(layout.plot.left + layout.plot.width).toBeLessThanOrEqual(width);
    }
  });

  it("draws a point outside the band as a triangle, and names it in words", () => {
    const { markup } = renderChart(chart(), 900);
    expect(markup.match(/class="dq-chart__out"/g)).toHaveLength(1);
    expect(markup).toContain("4,118 rows, below the range");
    expect(markup).toContain(`aria-label="${chart().summary}"`);
  });

  it("bands only the points Elementary had enough history to expect, and a lone one as a bar", () => {
    const { markup } = renderChart(chart(), 900);
    expect(markup.match(/<path class="dq-chart__band"/g)).toHaveLength(1);
    const file = examples.monthlyWithWarnings();
    file.series[0].points = file.series[0].points.map((point, i, all) =>
      i === all.length - 1 ? point : { ...point, expected_min: null, expected_max: null },
    );
    const lone = view(lane(file, "monthly"), MISSING).sections.chart;
    const drawn = renderChart(lone, 900).markup;
    expect(drawn).not.toContain('<path class="dq-chart__band"');
    expect(drawn.match(/<rect class="dq-chart__band"/g)).toHaveLength(1);
  });

  it("never lets two axis labels touch, at any width from a small phone to a laptop", () => {
    const hourly = examples.hourlyWithWarning();
    hourly.series = [
      {
        table: "preview_fixture__alerts",
        metric: "freshness",
        points: Array.from({ length: 48 }, (_, i) => ({
          at: new Date(Date.UTC(2026, 9, 6, i)).toISOString(),
          value: 3600 + (i % 5) * 600,
          expected_min: null,
          expected_max: null,
        })),
      },
    ];
    const week = view(MISSING, lane(examples.hourlyManyProblems(), "hourly")).sections.chart;
    expect(week.points).toHaveLength(168);
    const charts = [chart(), view(MISSING, lane(hourly, "hourly")).sections.chart, week];
    for (const drawn of charts) {
      for (let width = 300; width <= 1300; width += 10) {
        const layout = chartLayout(drawn, width);
        const labels = axisLabels(drawn, layout.xs, width, layout.plot.width);
        expect(labels[0].i).toBe(0);
        expect(labels.at(-1).i).toBe(drawn.points.length - 1);
        for (let i = 1; i < labels.length; i += 1) {
          expect(labels[i].start - labels[i - 1].end).toBeGreaterThanOrEqual(10);
        }
        for (const label of labels) {
          expect(label.start).toBeGreaterThanOrEqual(0);
          expect(label.end).toBeLessThanOrEqual(width);
        }
      }
    }
  });

  it("names the day on an hourly axis that spans more than one, and only the time on one that does not", () => {
    const week = view(MISSING, lane(examples.hourlyManyProblems(), "hourly")).sections.chart;
    const layout = chartLayout(week, 900);
    const texts = axisLabels(week, layout.xs, 900, layout.plot.width).map((label) => label.text);
    expect(texts.length).toBeGreaterThan(1);
    for (const text of texts) expect(text).toMatch(/^\d{1,2} [A-Z][a-z]{2} \d{2}:\d{2}$/);
    const day = { ...week, points: week.points.slice(-12) };
    const sameDay = chartLayout(day, 900);
    for (const label of axisLabels(day, sameDay.xs, 900, sameDay.plot.width)) expect(label.text).toMatch(/^\d{2}:\d{2}$/);
  });

  it("finds the point nearest the pointer", () => {
    expect(nearestPoint([10, 50, 90], 61)).toBe(1);
    expect(nearestPoint([10, 50, 90], 0)).toBe(0);
    expect(nearestPoint([10, 50, 90], 400)).toBe(2);
  });

  it("starts a count's axis no lower than zero, however far Elementary's band reaches", () => {
    const file = examples.monthlyWithWarnings();
    file.series[0].points = file.series[0].points.map((point) => ({ ...point, value: 3, expected_min: -40, expected_max: 20 }));
    const layout = chartLayout(view(lane(file, "monthly"), MISSING).sections.chart, 900);
    expect(layout.ticks[0].value).toBe(0);
    expect(layout.ticks[0].label).toBe(formatCount(0));
  });
});

describe("classes the page uses", () => {
  const css = read("../styles/site.css");
  const defined = new Set([...css.matchAll(/\.(dq-[\w-]+)/g)].map((m) => m[1]));

  // Classes that are there for the markup's own sake and carry no rule. Each
  // is named with the reason, so adding one is a decision rather than a way
  // to quiet the test.
  const HOOKS = {
    "dq-item--warn": "a warning's stripe is the default, so its modifier needs no rule of its own",
    "dq-chart__tick": "its text is styled by `.dq-chart__svg text`, with every other label in the chart",
    "dq-chart__hit": "a transparent rectangle for the pointer, drawn with fill set on the element",
  };

  it("hides an element with the hidden attribute whatever display its class sets", () => {
    // `.dq-item { display: grid }` beat the browser's own [hidden] rule in round 2's prototype list.
    expect(css).toMatch(/\.dq \[hidden\] \{\s*display: none !important;\s*\}/);
  });

  it("defines every dq- class the page and its markup name", () => {
    const markup = [
      read("../pages/data/quality/index.astro"),
      renderBody(lookingView()),
      renderBody(manyView()),
      renderCharted({ from: "Needs a look", table: "t", column: "c", row: "dq-row-0" }),
      renderBody(view(MISSING, MISSING)),
      renderBody(view(lane(examples.monthlyLearning(), "monthly"), MISSING)),
      ...lookingView().cards.map(renderCard),
      ...view({ state: "loading" }, { state: "failed", status: 500 }).cards.map(renderCard),
      renderChart(lookingView().sections.chart, 900).markup,
    ].join("\n");
    const used = new Set(
      [...markup.matchAll(/class="([^"{]*)"/g)].flatMap((m) => m[1].split(/\s+/)).filter((c) => c.startsWith("dq-")),
    );
    expect([...used].filter((c) => !defined.has(c) && !(c in HOOKS))).toEqual([]);
  });
});
