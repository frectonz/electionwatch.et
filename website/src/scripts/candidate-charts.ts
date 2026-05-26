// Shared ECharts setup for the candidate pages. Charts are intentionally clean:
// values live in the tooltip, so value axes carry no numeric labels; only the
// category axis is labelled. Colours are the site's orange/teal ballot combo.
import * as echarts from "echarts";
import {
  grad,
  radial,
  barShadow,
  offsetTooltip,
  narrowYLabels,
  tooltipBox,
  tipTitle,
  tipRow,
  MONO,
  MUTED,
  GRID,
  INK,
} from "@/scripts/chart-style";
import { fmt } from "@/lib/format";

const nf = (n: number) => fmt(n ?? 0);

type Stacked = { names: string[]; hopr: number[]; rc: number[] };
type Hist = { labels: string[]; counts: number[] };
type Slice = { name: string; value: number; color: string };

export function initCandidateCharts() {
  const charts: echarts.ECharts[] = [];
  const observed: HTMLElement[] = [];

  const mount = (id: string, build: (el: HTMLElement) => echarts.ECharts) => {
    const el = document.getElementById(id);
    if (!el) return;
    const chart = build(el);
    charts.push(chart);
    observed.push(el);
  };

  // Horizontal stacked HoPR/RC bar (region or party breakdowns). `labelsRight`
  // puts the category names on the right-hand side.
  const stackedBar = (id: string, labelsRight = false) =>
    mount(id, (el) => {
      const d = JSON.parse(el.dataset.chart!) as Stacked;
      const c = JSON.parse(el.dataset.colors!) as { hopr: string; rc: string };
      // What each bar counts (e.g. "candidates", "uncontested seats"), shown in
      // the tooltip total. Defaults to candidates for the existing breakdowns.
      const unit = el.dataset.unit ?? "candidates";
      const chart = echarts.init(el);
      chart.setOption({
        baseOption: {
          grid: { left: 4, right: 16, top: 8, bottom: 4, containLabel: true },
          tooltip: {
            trigger: "axis",
            axisPointer: { type: "shadow" },
            confine: true,
            enterable: false,
            transitionDuration: 0.2,
            position: offsetTooltip,
            ...tooltipBox,
            formatter: (
              p: {
                name: string;
                seriesName: string;
                value: number;
                marker: string;
              }[],
            ) => {
              const total = p.reduce((a, x) => a + (x.value || 0), 0);
              const rows = p
                .map((x) =>
                  tipRow(`${x.seriesName} ballot`, nf(x.value), x.marker),
                )
                .join("");
              return (
                tipTitle(p[0].name) + rows + tipRow(`Total ${unit}`, nf(total))
              );
            },
          },
          xAxis: {
            type: "value",
            axisLabel: { show: false },
            axisLine: { show: false },
            splitLine: { lineStyle: { color: GRID } },
          },
          yAxis: {
            type: "category",
            inverse: true,
            position: labelsRight ? "right" : "left",
            data: d.names,
            axisLabel: { color: MUTED, fontSize: 12 },
            axisTick: { show: false },
            axisLine: { show: false },
          },
          series: [
            {
              name: "HoPR",
              type: "bar",
              stack: "t",
              data: d.hopr,
              itemStyle: { color: grad(c.hopr), ...barShadow },
              barWidth: "62%",
            },
            {
              name: "Regional Council",
              type: "bar",
              stack: "t",
              data: d.rc,
              itemStyle: { color: grad(c.rc) },
            },
          ],
        },
        media: narrowYLabels,
      });
      return chart;
    });

  // Horizontal bar (education / party distribution); each row named beside its
  // bar. `labelsRight` moves the category names to the right-hand side.
  const histBar = (id: string, labelsRight = false) =>
    mount(id, (el) => {
      const d = JSON.parse(el.dataset.chart!) as Hist;
      const chart = echarts.init(el);
      chart.setOption({
        baseOption: {
          grid: { left: 4, right: 12, top: 4, bottom: 4, containLabel: true },
          tooltip: {
            trigger: "axis",
            axisPointer: { type: "shadow" },
            confine: true,
            position: offsetTooltip,
            ...tooltipBox,
            formatter: (p: { name: string; value: number }[]) =>
              tipTitle(p[0].name) + tipRow("Candidates", nf(p[0].value)),
          },
          xAxis: {
            type: "value",
            axisLabel: { show: false },
            axisLine: { show: false },
            splitLine: { lineStyle: { color: GRID } },
          },
          yAxis: {
            type: "category",
            inverse: true,
            position: labelsRight ? "right" : "left",
            data: d.labels,
            axisLabel: { color: MUTED, fontSize: 12 },
            axisTick: { show: false },
            axisLine: { show: false },
          },
          series: [
            {
              type: "bar",
              data: d.counts,
              itemStyle: {
                color: grad(INK, "h"),
                borderRadius: [0, 4, 4, 0],
                ...barShadow,
              },
              barWidth: "62%",
            },
          ],
        },
        media: narrowYLabels,
      });
      return chart;
    });

  // Concentric pie. Accepts a single ring (Slice[]) or several nested rings
  // ({ rings: Slice[][] }), e.g. gender on the inside, disability outside.
  const RADII: [string, string][] = [
    ["40%", "57%"],
    ["63%", "80%"],
  ];
  const donut = (id: string) =>
    mount(id, (el) => {
      const raw = JSON.parse(el.dataset.chart!) as
        | Slice[]
        | { rings: Slice[][] };
      const rings = Array.isArray(raw) ? [raw] : raw.rings;
      const total = rings[0].reduce((a, s) => a + s.value, 0);
      const chart = echarts.init(el);
      chart.setOption({
        tooltip: {
          trigger: "item",
          confine: true,
          ...tooltipBox,
          formatter: (p: {
            name: string;
            value: number;
            percent: number;
            marker: string;
          }) =>
            tipTitle(p.name) +
            tipRow("Candidates", nf(p.value), p.marker) +
            tipRow("Share", `${p.percent}%`),
        },
        legend: {
          bottom: 0,
          icon: "circle",
          itemWidth: 9,
          itemHeight: 9,
          itemGap: 12,
          textStyle: { color: MUTED, fontSize: 11 },
        },
        graphic: {
          type: "text",
          left: "center",
          top: "42%",
          style: {
            text: nf(total),
            textAlign: "center",
            textVerticalAlign: "middle",
            fill: INK,
            fontSize: 19,
            fontWeight: 700,
            fontFamily: MONO,
          },
        },
        series: rings.map((ring, i) => ({
          type: "pie",
          radius: RADII[i] ?? RADII[RADII.length - 1],
          center: ["50%", "44%"],
          avoidLabelOverlap: false,
          padAngle: 1.5,
          itemStyle: { borderColor: "#fff", borderWidth: 2, borderRadius: 3 },
          label: { show: false },
          data: ring.map((s) => ({
            name: s.name,
            value: s.value,
            itemStyle: { color: radial(s.color) },
          })),
        })),
      });
      return chart;
    });

  stackedBar("partyChart", true);
  stackedBar("uncontestedPartyChart", true);
  stackedBar("regionChart");
  donut("genderChart");
  histBar("eduChart");
  histBar("partyDistChart", true);

  const ro = new ResizeObserver(() => charts.forEach((c) => c.resize()));
  observed.forEach((el) => ro.observe(el));
}
