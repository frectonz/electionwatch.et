// Wire format for the polling-station map dataset, shared by the producer
// (scripts/build-ps-points.ts) and the consumers (the map components, via
// src/lib/map.ts). Kept dependency-free so the Node build script can import
// these types without pulling in maplibre-gl.

/** One constituency reference carried by the map dataset. */
export interface ConstituencyRef {
  slug: string;
  name: string;
  candidates: number;
}

/** A single point row:
 *  [lat, lon, regionIdx, registrationType(0=digital,1=manual), name, woreda,
 *   hoprConstituencyIdx, rcConstituencyIdx]. Indices of -1 mean "none". */
export type MapPoint = [
  lat: number,
  lon: number,
  regionIdx: number,
  typeIdx: number,
  name: string,
  woreda: string,
  hoprIdx: number,
  rcIdx: number,
];

/** The compact dataset the maps fetch at runtime (one global + per-region). */
export interface MapData {
  regions: string[];
  hoprC: ConstituencyRef[];
  rcC: ConstituencyRef[];
  points: MapPoint[];
}
