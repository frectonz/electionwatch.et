/** Thousands-separated integer, e.g. 12345 -> "12,345". */
export const fmt = (n: number) => n.toLocaleString("en-US");

/** Whole-number percentage of `n` out of `of` (0 when `of` is 0). */
export const pct = (n: number, of: number) =>
  of === 0 ? 0 : Math.round((n / of) * 100);

/** Vote-share label, without the unit: one decimal, and never rounds a real
 * share to "0" or "100". */
export const shareLabel = (n: number, of: number): string => {
  if (of === 0 || n === 0) return "0";
  const p = (n / of) * 100;
  if (p === 100) return "100";
  if (p < 0.1) return "<0.1";
  if (p > 99.9) return ">99.9";
  const s = p.toFixed(1);
  return s.endsWith(".0") ? p.toFixed(0) : s;
};

/** Ballot colours for the candidate charts: two tones derived from the primary
 * navy: HoPR (federal) the deeper shade, Regional Council a lighter tint. */
export const BALLOT_COLORS = { hopr: "#2d3370", rc: "#8b91cf" } as const;

/** Default chart/bar ink (the primary navy). */
export const INK = "#1f2455";

/** Brand gold accent (used where a non-navy highlight is needed). */
export const GOLD = "#c79a3a";

/** Muted text/axis grey. */
export const MUTED = "#7a7d92";

/** Neutral fill for the "no disability" share of the people ring. */
export const DISABILITY_GREY = "#dfe1ea";

/** Results colour coding: seats held by the incumbent vs anyone else. */
export const LEADER_COLOR = "#2d3370";
export const CHALLENGER_COLOR = "#c79a3a";

/** A recount, a re-run, or a seat whose winner is not yet attributed. */
export const OTHER_COLOR = "#c9ccd8";
export const NO_RESULT_COLOR = "#e6e8f0";

/** Seat-grid party hues, assigned in seat-count order so a party keeps its
 * colour across both chambers. Validated for contrast and deuteranopia. */
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
