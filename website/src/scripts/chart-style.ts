// Shared ECharts styling helpers so every chart on the site uses the same
// audit.et-inspired gradient fills and soft shadows.
import * as echarts from "echarts";
import { INK, MUTED } from "@/lib/format";

// Re-exported so chart scripts have a single import site for chart tokens.
export { INK, MUTED };

/** Monospace stack for numeric chart labels. */
export const MONO = "ui-monospace, SFMono-Regular, Menlo, monospace";

/** Faint split-line colour for value axes. */
export const GRID = "rgba(0,0,0,0.05)";

// On narrow containers, long category names (party / region / zone names)
// reserve so much horizontal room via `containLabel` that the bars get
// squished. Pass these as a chart's `media` (with the rest of the option under
// `baseOption`) to cap the y-axis label width and let ECharts ellipsise them;
// the full name stays available in the tooltip. Keyed to the chart's own width,
// not the viewport, so it works inside any column.
export const narrowYLabels = [
  {
    query: { maxWidth: 560 },
    option: {
      yAxis: { axisLabel: { width: 96, overflow: "truncate", fontSize: 11 } },
    },
  },
  {
    query: { maxWidth: 400 },
    option: {
      yAxis: { axisLabel: { width: 72, overflow: "truncate", fontSize: 10 } },
    },
  },
];

/** Keep an axis tooltip off the cursor so it never flickers under the pointer. */
export const offsetTooltip = (
  pt: number[],
  _p: unknown,
  _d: unknown,
  _r: unknown,
  size: { viewSize: number[]; contentSize: number[] },
) => {
  const [x, y] = pt;
  const [vw, vh] = size.viewSize;
  const [tw, th] = size.contentSize;
  let left = x + 18;
  if (left + tw > vw) left = x - tw - 18;
  return [left, Math.max(0, Math.min(y - th / 2, vh - th))];
};

/** Hex colour to an rgba() string at alpha `a`. */
export const hexA = (hex: string, a: number) => {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
};

/** Soft fill: a gradient from a translucent tint to the solid colour.
 * `dir` is "h" (left→right, for horizontal bars) or "v" (top→bottom). */
export const grad = (color: string, dir: "h" | "v" = "h") => {
  const [x0, y0, x1, y1] = dir === "h" ? [0, 0, 1, 0] : [0, 0, 0, 1];
  return new echarts.graphic.LinearGradient(x0, y0, x1, y1, [
    { offset: 0, color: hexA(color, 0.45) },
    { offset: 1, color },
  ]);
};

/** Radial fill for pie slices: lighter centre, solid rim. */
export const radial = (color: string) =>
  new echarts.graphic.RadialGradient(0.5, 0.5, 0.9, [
    { offset: 0, color: hexA(color, 0.7) },
    { offset: 1, color },
  ]);

/** Subtle drop shadow shared by bar series. */
export const barShadow = {
  shadowBlur: 8,
  shadowColor: "rgba(31, 36, 85, 0.12)",
  shadowOffsetY: 2,
};
