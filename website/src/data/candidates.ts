import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "../../../candidates/data/json");

export type Body = "hopr" | "rc";

export const BODY_LABEL: Record<Body, string> = {
  hopr: "House of People's Representatives",
  rc: "Regional Council",
};
export const BODY_SHORT: Record<Body, string> = { hopr: "HoPR", rc: "RC" };

/** One candidate, as produced by candidates/extract.py. */
export type Candidate = {
  region: string;
  region_native: string;
  region_code: string;
  body: Body;
  /** Electoral district (HoPR) or sub-region (RC) the candidate runs in. */
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
};

export type Party = {
  /** Stable positional id ("party-N"); party names are Amharic. */
  slug: string;
  /** Amharic name, as printed on the candidate lists. */
  name: string;
  /** English name (official where one exists, else a best-effort translation). */
  name_en: string;
  /** Slug into the party-profile dataset (/parties/[slug]) when one exists. */
  profile_slug: string | null;
  candidates: number;
  hopr: number;
  rc: number;
};

/** A constituency on the candidate side, pre-joined to its polling stations
 * by candidates/extract.py (matched on constituency name, joined by code). */
export type CandidateConstituency = {
  slug: string;
  region_slug: string;
  region: string;
  region_code: string;
  body: Body;
  name: string;
  candidates: number;
  parties: number;
  /** Polling stations in this constituency (0 when no station match was found). */
  polling_stations: number;
  /** Matched polling-station constituency codes (join key to that dataset). */
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
/** Reverse bridge: party-profile slug -> the candidate party (for /parties). */
export const partyByProfileSlug = new Map(
  candidateParties
    .filter((p) => p.profile_slug)
    .map((p) => [p.profile_slug as string, p]),
);

/** Look up a candidate constituency by body + region + name (candidate side). */
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

// Polling-station constituency code -> candidate constituency, so the
// polling-stations pages can link each constituency to its candidates.
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

/** Load every candidate (all regions + bodies). Used by party pages. */
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

/**
 * Load the candidate list for one region + body on demand. The combined dataset
 * is large, so pages load only the slice they render.
 */
export function loadCandidates(regionSlug: string, body: Body): Candidate[] {
  const file = path.join(ROOT, "candidates", `${regionSlug}_${body}.json`);
  if (!fs.existsSync(file)) return [];
  return JSON.parse(fs.readFileSync(file, "utf-8")) as Candidate[];
}
