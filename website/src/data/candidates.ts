import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { BALLOT_COLORS, GOLD, DISABILITY_GREY } from "@/lib/format";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "../../../candidates/data/json");

export type Body = "hopr" | "rc";

export const BODY_LABEL: Record<Body, string> = {
  hopr: "House of People's Representatives",
  rc: "Regional Council",
};
export const BODY_SHORT: Record<Body, string> = { hopr: "HoPR", rc: "RC" };

export type Candidate = {
  region: string;
  region_native: string;
  region_code: string;
  body: Body;
  constituency: string;
  candidate_id: string;
  full_name: string;
  gender: string;
  disability: boolean;
  party: string;
  education: string;
};

export type CandidateRegion = {
  slug: string;
  code: string;
  name: string;
  name_native: string;
  candidates: number;
  hopr: number;
  rc: number;
  hopr_constituencies: number;
  rc_constituencies: number;
  rc_seats: number;
};

export type Party = {
  slug: string;
  name: string;
  name_en: string;
  profile_slug: string | null;
  candidates: number;
  hopr: number;
  rc: number;
};

export type CandidateConstituency = {
  slug: string;
  region_slug: string;
  region: string;
  region_code: string;
  body: Body;
  name: string;
  candidates: number;
  parties: number;
  seats: number | null;
  seats_estimated: boolean;
  polling_stations: number;
  polling_station_codes: string[];
};

export type CandidatesIndex = {
  total_candidates: number;
  by_body: Record<Body, number>;
  hopr_constituency_count: number;
  rc_constituency_count: number;
  region_count: number;
  party_count: number;
  with_disability: number;
  by_gender: Record<string, number>;
  by_education: Record<string, number>;
  files: { file: string; region: string; body: Body; candidates: number }[];
};

function readJSON<T>(...segments: string[]): T {
  return JSON.parse(
    fs.readFileSync(path.join(ROOT, ...segments), "utf-8"),
  ) as T;
}

export const candidatesIndex = readJSON<CandidatesIndex>("index.json");
export const candidateRegions = readJSON<CandidateRegion[]>("regions.json");
export const candidateParties = readJSON<Party[]>("parties.json");

const constituenciesFile = readJSON<{
  hopr: CandidateConstituency[];
  rc: CandidateConstituency[];
}>("constituencies.json");

export const hoprCandidateConstituencies = constituenciesFile.hopr;
export const rcCandidateConstituencies = constituenciesFile.rc;

export const candidateRegionBySlug = new Map(
  candidateRegions.map((r) => [r.slug, r]),
);

export const partyBySlug = new Map(candidateParties.map((p) => [p.slug, p]));
export const partyByName = new Map(candidateParties.map((p) => [p.name, p]));
export const partySlugByName = new Map(
  candidateParties.map((p) => [p.name, p.slug]),
);
export const partyByProfileSlug = new Map(
  candidateParties
    .filter((p) => p.profile_slug)
    .map((p) => [p.profile_slug as string, p]),
);

const slugifyName = (name: string): string =>
  name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");

const urlSlugById = new Map<string, string>();
export const partyByUrlSlug = new Map<string, Party>();
{
  const used = new Set<string>();
  for (const p of candidateParties) {
    const base = p.profile_slug || slugifyName(p.name_en) || p.slug;
    let s = base;
    for (let n = 2; used.has(s); n++) s = `${base}-${n}`;
    used.add(s);
    urlSlugById.set(p.slug, s);
    partyByUrlSlug.set(s, p);
  }
}

export const partyUrlSlug = (p: Party): string =>
  urlSlugById.get(p.slug) ?? p.slug;

const constituencyByKey = new Map<string, CandidateConstituency>();
for (const c of [
  ...hoprCandidateConstituencies,
  ...rcCandidateConstituencies,
]) {
  constituencyByKey.set(`${c.body}|${c.region}|${c.name}`, c);
}
export function findConstituency(
  body: Body,
  region: string,
  name: string,
): CandidateConstituency | undefined {
  return constituencyByKey.get(`${body}|${region}|${name}`);
}

export function candidateConstituencies(body: Body): CandidateConstituency[] {
  return body === "hopr"
    ? hoprCandidateConstituencies
    : rcCandidateConstituencies;
}

const byStationCode: Record<Body, Map<string, CandidateConstituency>> = {
  hopr: new Map(),
  rc: new Map(),
};
for (const c of hoprCandidateConstituencies)
  for (const code of c.polling_station_codes) byStationCode.hopr.set(code, c);
for (const c of rcCandidateConstituencies)
  for (const code of c.polling_station_codes) byStationCode.rc.set(code, c);

export function candidateConstituencyByStation(
  body: Body,
  stationCode: string,
): CandidateConstituency | undefined {
  return byStationCode[body].get(stationCode);
}

export function loadAllCandidates(): Candidate[] {
  const out: Candidate[] = [];
  for (const r of candidateRegions) {
    out.push(
      ...loadCandidates(r.slug, "hopr"),
      ...loadCandidates(r.slug, "rc"),
    );
  }
  return out;
}

export function loadCandidates(regionSlug: string, body: Body): Candidate[] {
  const file = path.join(ROOT, "candidates", `${regionSlug}_${body}.json`);
  if (!fs.existsSync(file)) return [];
  return JSON.parse(fs.readFileSync(file, "utf-8")) as Candidate[];
}

export const regionSlugByName = new Map(
  candidateRegions.map((r) => [r.name, r.slug]),
);

export type RegionAgg = {
  name: string;
  slug: string;
  total: number;
  hopr: number;
  rc: number;
};

export function regionAggregation(candidates: Candidate[]): RegionAgg[] {
  const agg = new Map<string, RegionAgg>();
  for (const c of candidates) {
    const a = agg.get(c.region) ?? {
      name: c.region,
      slug: regionSlugByName.get(c.region) ?? "",
      total: 0,
      hopr: 0,
      rc: 0,
    };
    a.total++;
    if (c.body === "hopr") a.hopr++;
    else a.rc++;
    agg.set(c.region, a);
  }
  return [...agg.values()].sort((a, b) => b.total - a.total);
}

export function peopleRings(
  female: number,
  male: number,
  disabled: number,
  total: number,
) {
  return {
    rings: [
      [
        { name: "Male", value: male, color: BALLOT_COLORS.rc },
        { name: "Female", value: female, color: BALLOT_COLORS.hopr },
      ],
      [
        { name: "Has disability", value: disabled, color: GOLD },
        {
          name: "No disability",
          value: total - disabled,
          color: DISABILITY_GREY,
        },
      ],
    ],
  };
}

export type CountChart = { labels: string[]; counts: number[] };

export function countChart(entries: [string, number][]): CountChart {
  const sorted = [...entries].sort((a, b) => b[1] - a[1]);
  return { labels: sorted.map(([k]) => k), counts: sorted.map(([, v]) => v) };
}

export function educationChart(candidates: Candidate[]): CountChart {
  const counts = new Map<string, number>();
  for (const c of candidates) {
    const key = c.education || "Not Specified";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return countChart([...counts.entries()]);
}

export const EDU_LEVELS: string[] = [
  "Doctorate",
  "Master of Law",
  "Master of Science",
  "Master of Arts",
  "Bachelor of Law",
  "Bachelor of Science",
  "Bachelor of Arts",
  "High School",
  "Middle School",
  "Primary School",
  "No Education",
];

export type EduByParty = {
  order: { key: string; label: string }[];
  byTier: Record<
    string,
    { labels: string[]; counts: number[]; totals: number[]; shares: number[] }
  >;
};

export function educationTiersByParty(
  candidates: Candidate[],
  topN = 15,
): EduByParty {
  const levels = new Set(EDU_LEVELS);
  const agg = new Map<string, { total: number; levels: Map<string, number> }>();
  for (const c of candidates) {
    const name = partyByName.get(c.party)?.name_en ?? c.party;
    let a = agg.get(name);
    if (!a) {
      a = { total: 0, levels: new Map() };
      agg.set(name, a);
    }
    a.total++;
    const e = c.education || "";
    if (levels.has(e)) a.levels.set(e, (a.levels.get(e) ?? 0) + 1);
  }

  const byTier: EduByParty["byTier"] = {};
  for (const level of EDU_LEVELS) {
    const ranked = [...agg.entries()]
      .map(([name, a]) => ({
        name,
        count: a.levels.get(level) ?? 0,
        total: a.total,
      }))
      .filter((r) => r.count > 0)
      .sort((a, b) => b.count - a.count || b.total - a.total)
      .slice(0, topN);
    byTier[level] = {
      labels: ranked.map((r) => r.name),
      counts: ranked.map((r) => r.count),
      totals: ranked.map((r) => r.total),
      shares: ranked.map((r) => Math.round((r.count / r.total) * 100)),
    };
  }

  return {
    order: EDU_LEVELS.map((l) => ({ key: l, label: l })),
    byTier,
  };
}

export function partyDistChart(candidates: Candidate[]): CountChart {
  const counts = new Map<string, number>();
  for (const c of candidates)
    counts.set(c.party, (counts.get(c.party) ?? 0) + 1);
  return countChart(
    [...counts.entries()].map(([name, n]) => [
      partyByName.get(name)?.name_en ?? name,
      n,
    ]),
  );
}
