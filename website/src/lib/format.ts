export const fmt = (n: number) => n.toLocaleString("en-US");

export const pct = (n: number, of: number) =>
  of === 0 ? 0 : Math.round((n / of) * 100);

export const shareLabel = (n: number, of: number): string => {
  if (of === 0 || n === 0) return "0";
  const p = (n / of) * 100;
  if (p === 100) return "100";
  if (p < 0.1) return "<0.1";
  if (p > 99.9) return ">99.9";
  const s = p.toFixed(1);
  return s.endsWith(".0") ? p.toFixed(0) : s;
};

export const BALLOT_COLORS = { hopr: "#2d3370", rc: "#8b91cf" } as const;

export const INK = "#1f2455";

export const GOLD = "#c79a3a";

export const MUTED = "#7a7d92";

export const DISABILITY_GREY = "#dfe1ea";

export const LEADER_COLOR = "#2d3370";
export const CHALLENGER_COLOR = "#c79a3a";

export const OTHER_COLOR = "#c9ccd8";
export const NO_RESULT_COLOR = "#e6e8f0";

export const SEAT_HUES = [
  "#bf8b16",
  "#12876b",
  "#8552e0",
  "#c2306b",
  "#c85a18",
  "#2f93c4",
] as const;

export const INDEPENDENT_COLOR = "#5f6473";

export function timestamp(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

export function slugifyTopic(topic: string): string {
  return (
    "t-" +
    topic
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
  );
}
