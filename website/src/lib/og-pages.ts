import { allParties, allDebates } from "@/data";
import {
  candidateRegions,
  candidateParties,
  partyUrlSlug,
} from "@/data/candidates";
import { regions as pollingRegions } from "@/data/pollingStations";

export interface OgPage {
  title: string;
  description: string;
}

const TAGLINE = "Ethiopia's 7th General Election";

export const ogPages: Record<string, OgPage> = Object.fromEntries([
  [
    "index",
    {
      title: "electionwatch.et",
      description: `Open datasets on ${TAGLINE}: candidates, polling stations, party debates, and positions. Every record links to its source.`,
    },
  ],
  [
    "data",
    {
      title: "Data",
      description: `Open datasets on ${TAGLINE} — candidates, polling stations, and debates.`,
    },
  ],
  [
    "parties",
    {
      title: "Parties",
      description: `Parties on the ballot for ${TAGLINE}, with debate positions where available.`,
    },
  ],
  [
    "about",
    {
      title: "About",
      description: `An independent open-data portal for ${TAGLINE}, with every record linked to its source.`,
    },
  ],

  [
    "data/candidates",
    {
      title: "Candidates",
      description: `Every candidate registered for ${TAGLINE}, structured by region, constituency, and party.`,
    },
  ],
  [
    "results",
    {
      title: "Results",
      description: `The declared results of ${TAGLINE}: the seats each party won in the federal and regional councils.`,
    },
  ],
  [
    "data/polling-stations",
    {
      title: "Polling Stations",
      description: `Map and structured data for every NEBE polling station in ${TAGLINE}.`,
    },
  ],
  [
    "data/debates",
    {
      title: "Debates",
      description: `Debate broadcasts from ${TAGLINE}, analyzed question by question.`,
    },
  ],

  ...allParties.map((p): [string, OgPage] => [
    `parties/${p.slug}`,
    {
      title: p.name,
      description: `Positions and debate appearances for ${p.name} during ${TAGLINE}.`,
    },
  ]),

  ...candidateRegions.map((r): [string, OgPage] => [
    `data/candidates/${r.slug}`,
    {
      title: `${r.name} — Candidates`,
      description: `${r.candidates.toLocaleString()} candidates across ${r.name} for ${TAGLINE}: ${r.hopr.toLocaleString()} HoPR and ${r.rc.toLocaleString()} Regional Council.`,
    },
  ]),

  ...candidateParties.map((p): [string, OgPage] => [
    `data/candidates/party/${partyUrlSlug(p)}`,
    {
      title: `${p.name_en} — Candidates`,
      description: `${p.candidates.toLocaleString()} candidates fielded by ${p.name_en} in ${TAGLINE}.`,
    },
  ]),

  ...pollingRegions.map((r): [string, OgPage] => [
    `data/polling-stations/${r.slug}`,
    {
      title: `${r.name} — Polling Stations`,
      description: `${r.stations.toLocaleString()} polling stations in ${r.name} for ${TAGLINE}.`,
    },
  ]),

  ...allDebates.map((d): [string, OgPage] => [
    `data/debates/${d.meta.video_id}`,
    {
      title: d.analysis.title,
      description: `Analysis of the ${d.analysis.title} debate during ${TAGLINE}.`,
    },
  ]),
]);

export function ogImageFor(pathname: string): string {
  const key = pathname.replace(/^\/+|\/+$/g, "") || "index";
  return ogPages[key] ? `/og/${key}.png` : "/og/index.png";
}
