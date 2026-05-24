import type { APIRoute } from "astro";
import {
  loadAllCandidates,
  partyByName,
  partyUrlSlug,
  findConstituency,
} from "@/data/candidates";

// Compact, client-fetched search index for /candidates. Each candidate is a
// positional tuple (not an object) to keep the payload small across ~10k rows:
//   [name, partyEn, partySlug, region, constituency, conSlug, body, gender,
//    education, disability]
// The order is mirrored by src/scripts/candidate-search.ts.
export const GET: APIRoute = () => {
  const rows = loadAllCandidates().map((c) => {
    const party = partyByName.get(c.party);
    const con = findConstituency(c.body, c.region, c.constituency);
    return [
      c.full_name,
      party?.name_en ?? c.party,
      party ? partyUrlSlug(party) : "",
      c.region,
      c.constituency,
      con?.slug ?? "",
      c.body,
      c.gender,
      c.education,
      c.disability ? 1 : 0,
    ];
  });

  return new Response(JSON.stringify(rows), {
    headers: { "Content-Type": "application/json" },
  });
};
