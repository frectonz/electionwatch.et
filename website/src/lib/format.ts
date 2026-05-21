/** Thousands-separated integer, e.g. 12345 -> "12,345". */
export const fmt = (n: number) => n.toLocaleString("en-US");

/** Whole-number percentage of `n` out of `of` (0 when `of` is 0). */
export const pct = (n: number, of: number) =>
  of === 0 ? 0 : Math.round((n / of) * 100);

/** Ballot colours for the candidate charts: two tones derived from the primary
 * navy: HoPR (federal) the deeper shade, Regional Council a lighter tint. */
export const BALLOT_COLORS = { hopr: "#2d3370", rc: "#8b91cf" } as const;

/** Default chart/bar ink (the primary navy). */
export const INK = "#1f2455";

/** Brand gold accent (used where a non-navy highlight is needed). */
export const GOLD = "#c79a3a";

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
