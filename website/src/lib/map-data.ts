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
 *   hoprConstituencyIdx, rcConstituencyIdx, srcIdx]. Indices of -1 mean
 *  "none". srcIdx 0 is a NEBE-published GPS position; srcIdx 1 is a station
 *  NEBE published without coordinates, placed at random around its woreda's
 *  centre (Amhara). */
export type MapPoint = [
  lat: number,
  lon: number,
  regionIdx: number,
  typeIdx: number,
  name: string,
  woreda: string,
  hoprIdx: number,
  rcIdx: number,
  srcIdx: number,
];

/** The compact dataset the maps fetch at runtime (one global + per-region). */
export interface MapData {
  regions: string[];
  hoprC: ConstituencyRef[];
  rcC: ConstituencyRef[];
  points: MapPoint[];
}
