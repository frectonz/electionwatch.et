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
const CONSTITUENCY_DIR = path.join(REGION_DIR, "constituencies");

interface RegionMeta {
  name: string;
  slug: string;
}

interface ConstituencyRecord {
  slug: string;
  polling_stations: number;
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
  polling_station_code: string;
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

// Deterministic scatter for stations that only have a woreda centroid: a
// sunflower spiral around the centre with seeded jitter, so every station in
// the woreda gets its own stable, non-overlapping position without ever
// claiming station-level precision (the popup and page captions say so).
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
const SPACING = 0.009; // degrees between neighbouring dots, ~1 km
const MIN_SEP = 0.003; // degrees, ~330 m floor between any two scattered dots

const fnv = (s: string) => {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
};
const mulberry32 = (a: number) => () => {
  a |= 0;
  a = (a + 0x6d2b79f5) | 0;
  let t = Math.imul(a ^ (a >>> 15), 1 | a);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

/** polling_station_code -> scattered [lat, lon] for woreda-centroid stations. */
function scatterDerived(
  records: StationRecord[],
): Map<string, [number, number]> {
  const byCentroid = new Map<string, StationRecord[]>();
  for (const r of records) {
    if (r.coordinate_source !== "woreda_centroid" || r.latitude == null)
      continue;
    const key = `${r.latitude},${r.longitude}`;
    if (!byCentroid.has(key)) byCentroid.set(key, []);
    byCentroid.get(key)!.push(r);
  }

  // Spatial hash over placed dots so nearby woredas (a town centroid inside
  // its rural woreda, for example) cannot interleave dots closer than MIN_SEP.
  const grid = new Map<string, [number, number][]>();
  const cellOf = (lat: number, lon: number) =>
    `${Math.floor(lat / MIN_SEP)},${Math.floor(lon / MIN_SEP)}`;
  const collides = (lat: number, lon: number) => {
    const ci = Math.floor(lat / MIN_SEP);
    const cj = Math.floor(lon / MIN_SEP);
    for (let i = ci - 1; i <= ci + 1; i++)
      for (let j = cj - 1; j <= cj + 1; j++)
        for (const [plat, plon] of grid.get(`${i},${j}`) ?? [])
          if (Math.hypot(plat - lat, plon - lon) < MIN_SEP) return true;
    return false;
  };

  const out = new Map<string, [number, number]>();
  const groups = [...byCentroid.entries()].sort(([a], [b]) =>
    a.localeCompare(b),
  );
  for (const [key, group] of groups) {
    group.sort((a, b) =>
      a.polling_station_code.localeCompare(b.polling_station_code),
    );
    const clat = group[0].latitude!;
    const clon = group[0].longitude!;
    const rot = mulberry32(fnv(key))() * 2 * Math.PI;
    const lonScale = 1 / Math.cos((clat * Math.PI) / 180);
    group.forEach((r, k) => {
      const rand = mulberry32(fnv(r.polling_station_code));
      const radius = SPACING * Math.sqrt(k + 0.5);
      const theta = rot + k * GOLDEN_ANGLE;
      let lat = 0;
      let lon = 0;
      for (let attempt = 0; attempt < 80; attempt++) {
        const spread = SPACING * Math.min(0.5 + attempt * 0.25, 4);
        const dx = radius * Math.cos(theta) + (rand() - 0.5) * spread;
        const dy = radius * Math.sin(theta) + (rand() - 0.5) * spread;
        lat = Math.round((clat + dy) * 1e5) / 1e5;
        lon = Math.round((clon + dx * lonScale) * 1e5) / 1e5;
        if (!collides(lat, lon)) break;
      }
      const cell = cellOf(lat, lon);
      if (!grid.has(cell)) grid.set(cell, []);
      grid.get(cell)!.push([lat, lon]);
      out.set(r.polling_station_code, [lat, lon]);
    });
  }
  return out;
}

// candidates/extract.py already matched each polling-station constituency to the
// candidate constituency voted on there and emitted station_links.json keyed by
// polling-station constituency *code*. We just look it up — no name matching here.
function loadStationLinks(): StationLinks {
  const file = path.join(CAND_JSON, "station_links.json");
  if (!fs.existsSync(file)) return { hopr: {}, rc: {} };
  return JSON.parse(fs.readFileSync(file, "utf-8")) as StationLinks;
}

// Builds the compact dataset(s) the map fetches at runtime: one global file and
// one per region. Each point carries the HoPR and RC candidate constituencies
// voted on there (by index into the scope's `hoprC` / `rcC`) and a source flag:
// 0 for a NEBE-published GPS position, 1 for a station NEBE published without
// coordinates (Amhara), scattered deterministically around its woreda's centre.
// Stations with no coordinates at all are not included.
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

  // Every candidate constituency that matched a polling station, so we can emit
  // a (possibly empty) file for each one — the constituency page fetches by slug
  // and must not 404 when NEBE published no GPS coordinates for its stations.
  const constituenciesFile = JSON.parse(
    fs.readFileSync(path.join(CAND_JSON, "constituencies.json"), "utf-8"),
  ) as { hopr: ConstituencyRecord[]; rc: ConstituencyRecord[] };
  const constituencySlugs = [
    ...constituenciesFile.hopr,
    ...constituenciesFile.rc,
  ]
    .filter((c) => c.polling_stations > 0)
    .map((c) => c.slug);

  const makeScope = (): Scope => ({
    regions: [],
    points: [],
    hoprC: [],
    rcC: [],
  });
  const all = makeScope();
  const perRegion = new Map<string, Scope>();
  const perConstituency = new Map<string, Scope>();
  const constituencyScope = (slug: string): Scope => {
    let s = perConstituency.get(slug);
    if (!s) {
      s = makeScope();
      perConstituency.set(slug, s);
    }
    return s;
  };

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
    src: number,
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
      src,
    ]);

  const records = fs
    .readdirSync(SRC)
    .filter((f) => f.endsWith(".json"))
    .flatMap(
      (f) =>
        JSON.parse(
          fs.readFileSync(path.join(SRC, f), "utf-8"),
        ) as StationRecord[],
    );
  const scattered = scatterDerived(records);

  for (const r of records) {
    if (r.latitude == null) continue;
    let lat: number, lon: number, src: number;
    if (r.coordinate_source === "nebe") {
      lat = Math.round(r.latitude * 1e5) / 1e5;
      lon = Math.round(r.longitude! * 1e5) / 1e5;
      src = 0;
    } else if (r.coordinate_source === "woreda_centroid") {
      [lat, lon] = scattered.get(r.polling_station_code)!;
      src = 1;
    } else {
      continue;
    }
    const hoprRef = stationLinks.hopr[r.hopr_constituency_code];
    const rcRef = stationLinks.rc[r.rc_constituency_code];
    add(all, r, lat, lon, src, hoprRef, rcRef);
    const slug = slugByName.get(r.region);
    if (slug) {
      if (!perRegion.has(slug)) perRegion.set(slug, makeScope());
      add(perRegion.get(slug)!, r, lat, lon, src, hoprRef, rcRef);
    }
    // Each station belongs to one HoPR and one RC candidate constituency; emit
    // it into both, keyed by the candidate-side slug the page is built on.
    if (hoprRef)
      add(constituencyScope(hoprRef.slug), r, lat, lon, src, hoprRef, rcRef);
    if (rcRef)
      add(constituencyScope(rcRef.slug), r, lat, lon, src, hoprRef, rcRef);
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

  fs.mkdirSync(CONSTITUENCY_DIR, { recursive: true });
  for (const slug of constituencySlugs) {
    const scope = perConstituency.get(slug) ?? makeScope();
    fs.writeFileSync(
      path.join(CONSTITUENCY_DIR, `${slug}.json`),
      JSON.stringify(serialize(scope)),
    );
  }

  const kb = (
    fs.statSync(path.join(DEST_DIR, "polling-stations-map.json")).size / 1024
  ).toFixed(0);
  const derivedCount = all.points.filter((p) => p[8] === 1).length;
  console.log(
    `[ps-map] ${all.points.length - derivedCount} GPS-located points + ` +
      `${derivedCount} woreda-scattered points -> ` +
      `polling-stations-map.json (${kb} KB) + ${slugByName.size} region files` +
      ` + ${constituencySlugs.length} constituency files`,
  );
}

if (import.meta.url === `file://${process.argv[1]}`) {
  buildPollingStationPoints();
}
