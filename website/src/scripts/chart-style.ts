import * as echarts from "echarts";
import { INK, MUTED } from "@/lib/format";

export { INK, MUTED };

export const MONO = "ui-monospace, SFMono-Regular, Menlo, monospace";

export const GRID = "rgba(0,0,0,0.05)";

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

export const hexA = (hex: string, a: number) => {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
};

export const grad = (color: string, dir: "h" | "v" = "h") => {
  const [x0, y0, x1, y1] = dir === "h" ? [0, 0, 1, 0] : [0, 0, 0, 1];
  return new echarts.graphic.LinearGradient(x0, y0, x1, y1, [
    { offset: 0, color: hexA(color, 0.45) },
    { offset: 1, color },
  ]);
};

export const radial = (color: string) =>
  new echarts.graphic.RadialGradient(0.5, 0.5, 0.9, [
    { offset: 0, color: hexA(color, 0.7) },
    { offset: 1, color },
  ]);

export const barShadow = {
  shadowBlur: 8,
  shadowColor: "rgba(31, 36, 85, 0.12)",
  shadowOffsetY: 2,
};

export const tooltipBox = {
  backgroundColor: "rgba(255, 255, 255, 0.98)",
  borderColor: "rgba(0, 0, 0, 0.08)",
  borderWidth: 1,
  padding: [10, 12] as [number, number],
  textStyle: { color: INK, fontSize: 12, fontFamily: MONO },
  extraCssText:
    "border-radius:10px; box-shadow:0 10px 28px rgba(31,36,85,0.14);",
};

export const tipTitle = (title: string, sub?: string) =>
  `<div style="font-family:system-ui,sans-serif;font-weight:600;font-size:13px;color:${INK}">${title}` +
  (sub ? ` <span style="color:${MUTED};font-weight:400">${sub}</span>` : "") +
  `</div><div style="margin:7px 0;border-top:1px solid rgba(0,0,0,0.08)"></div>`;

export const tipRow = (label: string, value: string, marker = "") =>
  `<div style="display:flex;justify-content:space-between;gap:20px;line-height:1.7">` +
  `<span style="font-family:system-ui,sans-serif;color:${MUTED}">${marker}${label}</span>` +
  `<span style="font-weight:600">${value}</span></div>`;
