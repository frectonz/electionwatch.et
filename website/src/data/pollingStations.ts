import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PS_ROOT = path.resolve(__dirname, "../../../polling-stations/data/json");

export type RegistrationType = "digital" | "manual";

/** One polling station, as produced by polling-stations/extract.py. */
export type PollingStation = {
  no: number;
  region: string;
  region_native: string;
  region_code: string;
  zone: string;
  zone_code: string;
  woreda: string;
  woreda_code: string;
  kebele: string;
  kebele_code: string;
  /** Join key to constituencies.hopr[].code. */
  hopr_constituency_code: string;
  hopr_constituency: string;
  /** Join key to constituencies.rc[].code. */
  rc_constituency_code: string;
  rc_constituency: string;
  /** Stable unique identifier for the station. */
  polling_station_code: string;
  polling_station_id: string;
  ps_type: number | null;
  name: string;
  latitude: number | null;
  longitude: number | null;
  /** "nebe" when NEBE published a coordinate for the station, else null. */
  coordinate_source: "nebe" | null;
  registration_type: RegistrationType;
};

export type RegionStat = {
  slug: string;
  code: string;
  name: string;
  name_native: string;
  stations: number;
  digital: number;
  manual: number;
  with_coordinates: number;
};

export type Constituency = {
  code: string;
  name: string;
  region: string;
  stations: number;
};

export type PollingStationsIndex = {
  total_stations: number;
  by_registration_type: Record<RegistrationType, number>;
  with_coordinates: number;
  without_coordinates: number;
  /** Station counts by how their coordinate was sourced. */
  coordinate_sources: Record<string, number>;
  region_count: number;
  hopr_constituency_count: number;
  rc_constituency_count: number;
  files: {
    file: string;
    region: string;
    registration_type: RegistrationType;
    stations: number;
    with_coordinates: number;
  }[];
};

function readJSON<T>(...segments: string[]): T {
  return JSON.parse(
    fs.readFileSync(path.join(PS_ROOT, ...segments), "utf-8"),
  ) as T;
}

export const pollingStationsIndex =
  readJSON<PollingStationsIndex>("index.json");

export const regions: RegionStat[] = readJSON<RegionStat[]>("regions.json");

const constituenciesFile = readJSON<{
  hopr: Constituency[];
  rc: Constituency[];
}>("constituencies.json");
export const hoprConstituencies = constituenciesFile.hopr;
export const rcConstituencies = constituenciesFile.rc;

export const regionBySlug = new Map(regions.map((r) => [r.slug, r]));

/**
 * Load the full station list for one region + registration type on demand.
 * The combined dataset is large (~50k rows), so callers should load only the
 * slices they render rather than eagerly importing every file.
 */
export function loadStations(
  regionSlug: string,
  type: RegistrationType,
): PollingStation[] {
  const file = path.join(PS_ROOT, "stations", `${regionSlug}_${type}.json`);
  if (!fs.existsSync(file)) return [];
  return JSON.parse(fs.readFileSync(file, "utf-8")) as PollingStation[];
}
