import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import type { ConstituencyRef, MapData, MapPoint } from "../src/lib/map-data";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PS_JSON = path.resolve(__dirname, "../../polling-stations/data/json");
const CAND_JSON = path.resolve(__dirname, "../../candidates/data/json");
const SRC = path.join(PS_JSON, "stations");
const DEST_DIR = path.resolve(__dirname, "../public/data");
const REGION_DIR = path.join(DEST_DIR, "polling-stations-map");

interface RegionMeta {
  name: string;
  slug: string;
}

interface StationRecord {
  coordinate_source: string;
  latitude: number | null;
  longitude: number | null;
  region: string;
  registration_type: string;
  name: string;
  woreda: string;
  hopr_constituency_code: string;
  rc_constituency_code: string;
}

interface StationLinks {
  hopr: Record<string, ConstituencyRef>;
  rc: Record<string, ConstituencyRef>;
}

type Scope = {
  regions: string[];
  points: MapPoint[];
  hoprC: ConstituencyRef[];
  rcC: ConstituencyRef[];
};

// candidates/extract.py already matched each polling-station constituency to the
// candidate constituency voted on there and emitted station_links.json keyed by
// polling-station constituency *code*. We just look it up — no name matching here.
function loadStationLinks(): StationLinks {
  const file = path.join(CAND_JSON, "station_links.json");
  if (!fs.existsSync(file)) return { hopr: {}, rc: {} };
  return JSON.parse(fs.readFileSync(file, "utf-8")) as StationLinks;
}

// Builds the compact dataset(s) the map fetches at runtime: one global file and
// one per region. Only stations with NEBE-published GPS coordinates are
// included — NEBE left coordinates blank for many stations, and we do not invent
// locations for them. Each point also carries the HoPR and RC candidate
// constituencies voted on there (by index into the scope's `hoprC` / `rcC`).
export function buildPollingStationPoints() {
  if (!fs.existsSync(SRC)) {
    console.warn(`[ps-map] source dir not found, skipping: ${SRC}`);
    return;
  }

  const regionMeta = JSON.parse(
    fs.readFileSync(path.join(PS_JSON, "regions.json"), "utf-8"),
  ) as RegionMeta[];
  const slugByName = new Map(regionMeta.map((r) => [r.name, r.slug]));
  const stationLinks = loadStationLinks();

  const makeScope = (): Scope => ({
    regions: [],
    points: [],
    hoprC: [],
    rcC: [],
  });
  const all = makeScope();
  const perRegion = new Map<string, Scope>();

  const tableIdx = (
    table: ConstituencyRef[],
    ref?: ConstituencyRef,
  ): number => {
    if (!ref) return -1;
    let i = table.findIndex((t) => t.slug === ref.slug);
    if (i === -1) {
      i = table.length;
      table.push(ref);
    }
    return i;
  };
  const regionIdx = (scope: Scope, name: string): number => {
    let i = scope.regions.indexOf(name);
    if (i === -1) {
      i = scope.regions.length;
      scope.regions.push(name);
    }
    return i;
  };

  const add = (
    scope: Scope,
    r: StationRecord,
    lat: number,
    lon: number,
    hoprRef?: ConstituencyRef,
    rcRef?: ConstituencyRef,
  ) =>
    scope.points.push([
      lat,
      lon,
      regionIdx(scope, r.region),
      r.registration_type === "digital" ? 0 : 1,
      r.name,
      r.woreda,
      tableIdx(scope.hoprC, hoprRef),
      tableIdx(scope.rcC, rcRef),
    ]);

  for (const file of fs.readdirSync(SRC).filter((f) => f.endsWith(".json"))) {
    const records = JSON.parse(
      fs.readFileSync(path.join(SRC, file), "utf-8"),
    ) as StationRecord[];
    for (const r of records) {
      if (r.coordinate_source !== "nebe" || r.latitude == null) continue;
      const lat = Math.round(r.latitude * 1e5) / 1e5;
      const lon = Math.round(r.longitude! * 1e5) / 1e5;
      const hoprRef = stationLinks.hopr[r.hopr_constituency_code];
      const rcRef = stationLinks.rc[r.rc_constituency_code];
      add(all, r, lat, lon, hoprRef, rcRef);
      const slug = slugByName.get(r.region);
      if (slug) {
        if (!perRegion.has(slug)) perRegion.set(slug, makeScope());
        add(perRegion.get(slug)!, r, lat, lon, hoprRef, rcRef);
      }
    }
  }

  const serialize = (scope: Scope): MapData => ({
    regions: scope.regions,
    hoprC: scope.hoprC,
    rcC: scope.rcC,
    points: scope.points,
  });

  fs.mkdirSync(REGION_DIR, { recursive: true });
  fs.writeFileSync(
    path.join(DEST_DIR, "polling-stations-map.json"),
    JSON.stringify(serialize(all)),
  );
  for (const slug of slugByName.values()) {
    const scope = perRegion.get(slug) ?? makeScope();
    fs.writeFileSync(
      path.join(REGION_DIR, `${slug}.json`),
      JSON.stringify(serialize(scope)),
    );
  }

  const kb = (
    fs.statSync(path.join(DEST_DIR, "polling-stations-map.json")).size / 1024
  ).toFixed(0);
  console.log(
    `[ps-map] ${all.points.length} GPS-located points -> ` +
      `polling-stations-map.json (${kb} KB) + ${slugByName.size} region files`,
  );
}

if (import.meta.url === `file://${process.argv[1]}`) {
  buildPollingStationPoints();
}
