import { allDebates, allParties } from "./index";
import { pollingStationsIndex } from "./pollingStations";

export type DatasetStatus = "live" | "in-progress" | "planned";

export type DatasetMeta = {
  id: string;
  title: string;
  blurb: string;
  href: string;
  status: DatasetStatus;
  records: number;
  recordsLabel: string;
  sources: string[];
  updatedAt?: string;
};

const partiesWithPositions = allParties.filter(
  (p) => p.positions.length > 0,
).length;

export const datasets: DatasetMeta[] = [
  {
    id: "debates",
    title: "Debate Broadcasts",
    blurb:
      "Question-by-question breakdowns of every official debate. Each party answer, claim, and key point is linked back to the YouTube timestamp where it was spoken.",
    href: "/data/debates",
    status: "live",
    records: allDebates.length,
    recordsLabel: "broadcasts analysed",
    sources: ["ETV / NEBE", "Fana Medrek"],
  },
  {
    id: "party-positions",
    title: "Party Position Files",
    blurb:
      "Consolidated, citable position files for each party, aggregated across every debate appearance into a single dossier per party.",
    href: "/parties",
    status: "live",
    records: partiesWithPositions,
    recordsLabel: "party profiles with positions",
    sources: ["Debate transcripts"],
  },
  {
    id: "polling-stations",
    title: "Polling Stations",
    blurb:
      "Every registered polling station for the 7th General Election, structured by region, zone, woreda, kebele, and electoral constituency — with coordinates where the board published them.",
    href: "/data/polling-stations",
    status: "live",
    records: pollingStationsIndex.total_stations,
    recordsLabel: "polling stations",
    sources: ["NEBE"],
  },
];

export const liveDatasets = datasets.filter((d) => d.status === "live");
