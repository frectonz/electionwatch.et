export interface ConstituencyRef {
  slug: string;
  name: string;
  candidates: number;
}

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

export interface MapData {
  regions: string[];
  hoprC: ConstituencyRef[];
  rcC: ConstituencyRef[];
  points: MapPoint[];
}
