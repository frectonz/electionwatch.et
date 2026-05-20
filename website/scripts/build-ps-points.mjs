import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PS_JSON = path.resolve(__dirname, "../../polling-stations/data/json");
const SRC = path.join(PS_JSON, "stations");
const DEST_DIR = path.resolve(__dirname, "../public/data");
const REGION_DIR = path.join(DEST_DIR, "polling-stations-map");

// Builds the compact dataset(s) the map fetches at runtime: one global file and
// one per region. Only stations with NEBE-published GPS coordinates are
// included — NEBE left coordinates blank for many stations, and we do not invent
// locations for them.
export function buildPollingStationPoints() {
  if (!fs.existsSync(SRC)) {
    console.warn(`[ps-map] source dir not found, skipping: ${SRC}`);
    return;
  }

  const regionMeta = JSON.parse(
    fs.readFileSync(path.join(PS_JSON, "regions.json"), "utf-8"),
  );
  const slugByName = new Map(regionMeta.map((r) => [r.name, r.slug]));

  const makeScope = () => ({ regions: [], points: [] });
  const all = makeScope();
  const perRegion = new Map(); // slug -> scope

  const regionIdx = (scope, name) => {
    let i = scope.regions.indexOf(name);
    if (i === -1) {
      i = scope.regions.length;
      scope.regions.push(name);
    }
    return i;
  };

  const add = (scope, r, lat, lon) =>
    scope.points.push([
      lat,
      lon,
      regionIdx(scope, r.region),
      r.registration_type === "digital" ? 0 : 1,
      r.name,
      r.woreda,
    ]);

  for (const file of fs.readdirSync(SRC).filter((f) => f.endsWith(".json"))) {
    const records = JSON.parse(fs.readFileSync(path.join(SRC, file), "utf-8"));
    for (const r of records) {
      if (r.coordinate_source !== "nebe" || r.latitude == null) continue;
      const lat = Math.round(r.latitude * 1e5) / 1e5;
      const lon = Math.round(r.longitude * 1e5) / 1e5;
      add(all, r, lat, lon);
      const slug = slugByName.get(r.region);
      if (slug) {
        if (!perRegion.has(slug)) perRegion.set(slug, makeScope());
        add(perRegion.get(slug), r, lat, lon);
      }
    }
  }

  // [lat, lon, regionIdx, registrationType(0=digital,1=manual), name, woreda]
  const serialize = (scope) => ({
    regions: scope.regions,
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
