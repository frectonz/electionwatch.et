// The strip plot of every seat by the share of the vote its winner took,
// plus the page's ballot-toggle wiring.
import * as echarts from "echarts";
import {
  offsetTooltip,
  tooltipBox,
  tipTitle,
  tipRow,
  INK,
  MONO,
  MUTED,
  GRID,
} from "@/scripts/chart-style";
import { LEADER_COLOR, CHALLENGER_COLOR } from "@/lib/format";

export type Ballot = "hopr" | "rc";

/** [share, incumbent, seat, winner, party, slug] — see SeatDot in data/results. */
type Dot = [number, 0 | 1, string, string, string, string];
type ByBallot<T> = Record<Ballot, T>;

/** Wire every ballot toggle on the page to whatever listens for it. */
function wireBallots(onChange: (target: string, ballot: Ballot) => void) {
  document
    .querySelectorAll<HTMLElement>("[data-ballot-toggle]")
    .forEach((group) => {
      const target = group.dataset.ballotToggle!;
      const buttons = Array.from(
        group.querySelectorAll<HTMLButtonElement>("button[data-ballot]"),
      );
      buttons.forEach((btn) =>
        btn.addEventListener("click", () => {
          const ballot = btn.dataset.ballot as Ballot;
          buttons.forEach((b) => {
            const active = b === btn;
            b.setAttribute("aria-pressed", String(active));
            b.classList.toggle("bg-ew-shell", active);
            b.classList.toggle("text-white", active);
            b.classList.toggle("bg-ew-card", !active);
            b.classList.toggle("text-ew-text-dim", !active);
            b.classList.toggle("hover:text-ew-shell", !active);
          });
          onChange(target, ballot);
        }),
      );
    });
}

/** Show only the elements belonging to the chosen ballot. */
function swapPanels(target: string, ballot: Ballot) {
  document
    .querySelectorAll<HTMLElement>(`[data-ballot-panel="${target}"]`)
    .forEach((el) => {
      el.hidden = el.dataset.ballotValue !== ballot;
    });
}

export function initResultCharts() {
  const el = document.getElementById("chart-share");
  let chart: echarts.ECharts | null = null;
  let data: ByBallot<Dot[]> | null = null;

  // Deterministic jitter, so the picture is identical on every render.
  const jitter = (i: number) => ((i * 2654435761) % 1000) / 1000;

  const option = (dots: Dot[]) => ({
    grid: { left: 8, right: 20, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      trigger: "item",
      position: offsetTooltip,
      // The tooltip carries a link, so it must survive the mouse travelling
      // into it instead of vanishing the instant the cursor leaves the dot.
      enterable: true,
      hideDelay: 200,
      ...tooltipBox,
      formatter: (p: { value: [number, number]; data: { dot: Dot } }) => {
        const [share, , seat, winner, party, slug] = p.data.dot;
        return (
          tipTitle(seat) +
          tipRow("Elected", winner) +
          tipRow("Party", party) +
          tipRow("Share of the vote", `${share}%`) +
          `<a href="/data/candidates/c/${slug}" style="display:inline-block;` +
          `margin-top:7px;font-size:12px;font-weight:600;color:${INK};` +
          `text-decoration:none;font-family:system-ui,sans-serif">` +
          `See the full result &rsaquo;</a>`
        );
      },
    },
    xAxis: {
      type: "value",
      min: 0,
      max: 100,
      name: "share of the vote taken by the winner",
      nameLocation: "middle",
      nameGap: 30,
      nameTextStyle: { color: MUTED, fontSize: 11 },
      axisLabel: {
        color: MUTED,
        fontSize: 10,
        fontFamily: MONO,
        formatter: (v: number) => `${v}%`,
      },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: GRID } },
      splitLine: { lineStyle: { color: GRID } },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 1,
      axisLabel: { show: false },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
    },
    series: [
      {
        type: "scatter",
        symbolSize: 7,
        data: dots.map((dot, i) => ({
          value: [dot[0], jitter(i)],
          dot,
          itemStyle: {
            color: dot[1] ? LEADER_COLOR : CHALLENGER_COLOR,
            opacity: 0.55,
            borderColor: "#fff",
            borderWidth: 0.5,
          },
        })),
        z: 2,
      },
    ],
  });

  if (el?.dataset.dots) {
    data = JSON.parse(el.dataset.dots) as ByBallot<Dot[]>;
    chart = echarts.init(el);
    chart.setOption(option(data.hopr));
    // Clicking a dot is also the touch path; the hover tooltip is mouse-only.
    chart.on("click", (p) => {
      const dot = (p.data as { dot?: Dot })?.dot;
      if (dot) window.location.assign(`/data/candidates/c/${dot[5]}`);
    });
  }

  wireBallots((target, ballot) => {
    if (target === "share" && chart && data) {
      chart.setOption(option(data[ballot]), true);
    }
    swapPanels(target, ballot);
  });

  window.addEventListener("resize", () => chart?.resize());
}
