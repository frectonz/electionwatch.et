import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_ROOT = path.resolve(__dirname, "../../../transcripts/data");
const SYMBOLS_ROOT = path.resolve(__dirname, "../../../symbols/data");

export type PartyRegistryEntry = { name: string };

export type SymbolEntry = { slug: string; image: string };

export type Span = {
  start_index: number;
  end_index: number;
  start: number;
  end: number;
  youtube_url: string;
  embed_url: string;
};

export type PositionCitation = {
  video_id: string;
  excerpt: string;
  spans: Span[];
};

export type PartyPosition = {
  topic: string;
  position: string;
  citations: PositionCitation[];
};

export type PartyPositionsFile = {
  slug: string;
  name: string;
  positions: PartyPosition[];
};

export type DebateMeta = {
  video_id: string;
  source: string;
  upload_date: string;
  youtube_url: string;
  duration_seconds: number;
  title: string;
  parties: { name: string; slug: string }[];
};

export type DebateKeyPoint = {
  point: string;
  citations: Span[];
};

export type DebateAnswer = {
  party_slug: string;
  summary: string;
  key_points: DebateKeyPoint[];
  citations: Span[];
};

export type DebateQuestion = {
  asker: string;
  topic: string;
  question: string;
  citations: Span[];
  answers: DebateAnswer[];
};

export type DebateAnalysis = {
  video_id: string;
  title: string;
  source: string;
  upload_date: string;
  youtube_url: string;
  overall_topic: string;
  questions: DebateQuestion[];
};

export type Debate = {
  meta: DebateMeta;
  analysis: DebateAnalysis;
};

export type Party = {
  slug: string;
  name: string;
  /** Public URL of the party's ballot symbol, or null if none was extracted. */
  symbol: string | null;
  positions: PartyPosition[];
  debateCount: number;
};

const partiesRegistry: Record<string, PartyRegistryEntry> = JSON.parse(
  fs.readFileSync(path.join(DATA_ROOT, "parties.json"), "utf-8"),
);

// Symbols are synced into public/symbols/ at build time (see
// scripts/sync-symbols.mjs); map each party slug to its served URL.
const symbolsList: SymbolEntry[] = JSON.parse(
  fs.readFileSync(path.join(SYMBOLS_ROOT, "symbols.json"), "utf-8"),
);
const symbolBySlug = new Map(
  symbolsList.map((s) => [s.slug, `/symbols/${s.image}`]),
);

function readJSON<T>(file: string): T {
  return JSON.parse(fs.readFileSync(file, "utf-8")) as T;
}

function listMetaFiles(source: string): string[] {
  const dir = path.join(DATA_ROOT, source);
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".meta.json"))
    .map((f) => path.join(dir, f));
}

export const SOURCES = ["etv_nebe", "fana_medrek"] as const;
export type Source = (typeof SOURCES)[number];

export const SOURCE_LABELS: Record<Source, string> = {
  etv_nebe: "ETV / NEBE",
  fana_medrek: "Fana Medrek",
};

function loadDebatesForSource(source: Source): Debate[] {
  const debates: Debate[] = [];
  for (const metaFile of listMetaFiles(source)) {
    const meta = readJSON<DebateMeta>(metaFile);
    const analysisFile = metaFile.replace(".meta.json", ".analysis.json");
    if (!fs.existsSync(analysisFile)) continue;
    const analysis = readJSON<DebateAnalysis>(analysisFile);
    debates.push({ meta, analysis });
  }
  debates.sort((a, b) => (a.meta.upload_date < b.meta.upload_date ? 1 : -1));
  return debates;
}

export const debatesBySource: Record<Source, Debate[]> = {
  etv_nebe: loadDebatesForSource("etv_nebe"),
  fana_medrek: loadDebatesForSource("fana_medrek"),
};

export const allDebates: Debate[] = SOURCES.flatMap(
  (s) => debatesBySource[s],
).sort((a, b) => (a.meta.upload_date < b.meta.upload_date ? 1 : -1));

export function getDebate(videoId: string): Debate | null {
  return allDebates.find((d) => d.meta.video_id === videoId) ?? null;
}

function loadPositionsForSlug(slug: string): PartyPosition[] {
  const file = path.join(DATA_ROOT, "positions", `${slug}.json`);
  if (!fs.existsSync(file)) return [];
  return readJSON<PartyPositionsFile>(file).positions;
}

function countDebateAppearances(slug: string): number {
  return allDebates.filter((d) => d.meta.parties.some((p) => p.slug === slug))
    .length;
}

export const allParties: Party[] = Object.entries(partiesRegistry)
  .map(([slug, info]) => ({
    slug,
    name: info.name,
    symbol: symbolBySlug.get(slug) ?? null,
    positions: loadPositionsForSlug(slug),
    debateCount: countDebateAppearances(slug),
  }))
  .sort((a, b) => a.name.localeCompare(b.name));

export const partyBySlug = new Map(allParties.map((p) => [p.slug, p]));

export function partyName(slug: string): string {
  const name = partyBySlug.get(slug)?.name;
  if (!name) {
    throw new Error(
      `Party "${slug}" referenced but not registered in parties.json`,
    );
  }
  return name;
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
