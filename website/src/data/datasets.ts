import { allDebates, allParties } from "./index";
import { pollingStationsIndex } from "./pollingStations";
import { candidatesIndex } from "./candidates";

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
  /** Short description of where the underlying data came from. */
  sourceNote: string;
  /** Link to the primary source. */
  sourceUrl: string;
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
    sourceNote:
      "Transcribed from the official ETV/NEBE and Fana Medrek debate broadcasts on YouTube; every claim links to its video timestamp.",
    sourceUrl: "/data/debates",
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
    sourceNote:
      "Compiled from the debate analyses; each position links to the moment it was stated.",
    sourceUrl: "/data/debates",
  },
  {
    id: "polling-stations",
    title: "Polling Stations",
    blurb:
      "Every registered polling station for the 7th General Election, structured by region, zone, woreda, kebele, and electoral constituency, with coordinates where the board published them.",
    href: "/data/polling-stations",
    status: "live",
    records: pollingStationsIndex.total_stations,
    recordsLabel: "polling stations",
    sources: ["NEBE"],
    sourceNote: "Extracted from NEBE's regional polling-station PDFs.",
    sourceUrl: "https://nebe.org.et/en/List_of_polling_stations",
  },
  {
    id: "candidates",
    title: "Candidates",
    blurb:
      "Every candidate cleared for the 7th General Election, for the federal House of People's Representatives and the regional councils, with party, gender, and education, linked to the polling stations where each is voted on.",
    href: "/data/candidates",
    status: "live",
    records: candidatesIndex.total_candidates,
    recordsLabel: "candidates",
    sources: ["NEBE"],
    sourceNote:
      "Extracted from NEBE's published HoPR and Regional Council candidate lists.",
    sourceUrl: "https://nebe.org.et/en/candidate-list",
  },
];

export const liveDatasets = datasets.filter((d) => d.status === "live");
