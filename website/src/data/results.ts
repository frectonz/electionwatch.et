import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import {
  candidateConstituencies,
  loadCandidates,
  partyBySlug,
  partyUrlSlug,
  type Body,
} from "./candidates";
import {
  LEADER_COLOR,
  CHALLENGER_COLOR,
  OTHER_COLOR,
  SEAT_HUES,
  INDEPENDENT_COLOR,
} from "@/lib/format";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const RESULTS_ROOT = path.resolve(__dirname, "../../../results/data/json");

/** National registration / turnout / ballot figures from NEBE's summary sheet. */
export type ResultsSummary = {
  registered_voters: number;
  votes_cast: number;
  turnout_pct: number;
  abstained_pct: number;
  ballots_used: number;
  ballots_unused: number;
  ballots_invalid: number;
  /** NEBE excludes constituencies undergoing recounts or re-elections. */
  excludes_recounts_and_reruns: boolean;
  source_url: string;
  published: string;
};

/** One party's (or independent's) seat haul in one region. */
export type SeatRow = {
  /** Party name as printed in the results PDF (Amharic). */
  party: string;
  independent: boolean;
  /** Independent candidate's name, when `independent` is true. */
  candidate: string | null;
  /** Join key to candidates/{region}_{body}.json, when matched. */
  candidate_id: string | null;
  seats: number;
  /** Join key to the candidates dataset's parties.json, when matched. */
  party_slug: string | null;
  party_name_en: string | null;
  /** Join key to the party-profile dataset, when the party has a profile. */
  profile_slug: string | null;
};

export type RegionSeats = {
  region_slug: string;
  region: string;
  region_native: string;
  /** The region's total council seats (null where the PDF omits it). */
  council_seats: number | null;
  /** Seats decided so far (excludes recount / re-run constituencies). */
  decided_seats: number;
  won: SeatRow[];
};

export type PartySeatTotal = {
  party: string;
  party_slug: string | null;
  party_name_en: string | null;
  profile_slug: string | null;
  seats: number;
  /** Number of regions the party won seats in. */
  regions: number;
};

export type BodySeats = {
  regions: RegionSeats[];
  decided_seats: number;
  council_seats: number;
  parties: PartySeatTotal[];
  independents: { seats: number; candidates: number };
};

/** One elected candidate, as produced by results/extract.py. */
export type ElectedRow = {
  region_slug: string;
  /** Constituency as printed in the results PDF. */
  constituency: string;
  /** Join key to the candidates dataset's constituencies.json, when matched. */
  constituency_slug: string | null;
  /** Candidate name as printed in the results PDF. */
  candidate: string;
  candidate_id: string | null;
  /** Party (Amharic candidate-list name), resolved via the candidate match. */
  party: string | null;
  party_slug: string | null;
  party_name_en: string | null;
  profile_slug: string | null;
};

/** One candidate's votes in one constituency (region comes from the file). */
export type VoteRow = Omit<ElectedRow, "region_slug"> & {
  votes: number | null;
  elected: boolean;
};

// A body only appears once its sheet is fully transcribed, so both maps are partial.
export type ResultsIndex = {
  seats: Partial<
    Record<
      Body,
      {
        decided_seats: number;
        council_seats: number;
        parties: number;
        independent_seats: number;
      }
    >
  >;
  elected: Partial<Record<Body, number>>;
  votes_rows: number;
  match: Record<
    string,
    { rows: number; constituency_matched: number; candidate_matched: number }
  >;
  source_url: string;
  published: string;
  files: { file: string; region: string; body: Body; rows: number }[];
};

/** Read a file the results pipeline always produces; it ships with the repo. */
function read<T>(name: string): T {
  return JSON.parse(
    fs.readFileSync(path.join(RESULTS_ROOT, name), "utf-8"),
  ) as T;
}

export const resultsSeats = read<Record<Body, BodySeats>>("seats.json");
const resultsIndex = read<ResultsIndex>("index.json");
export const resultsSummary = read<ResultsSummary>("summary.json");
export const resultsElected = read<Record<Body, ElectedRow[]>>("elected.json");

/** Votes for one region + body. Absent until every page of the council's
 * vote sheet is transcribed, so callers must handle the empty case. */
export function votesFor(regionSlug: string, body: Body): VoteRow[] {
  const file = path.join(RESULTS_ROOT, "votes", `${regionSlug}_${body}.json`);
  if (!fs.existsSync(file)) return [];
  return JSON.parse(fs.readFileSync(file, "utf-8")) as VoteRow[];
}

/** True for a council whose per-candidate vote counts are published. */
export const hasVotes = (body: Body) =>
  resultsIndex.files.some((f) => f.body === body);

// --- Derived views ---------------------------------------------------------

const BODIES: Body[] = ["hopr", "rc"];

/** Every body the results cover, with its seat data. */
export const resultBodies = BODIES.map((key) => ({
  key,
  data: resultsSeats[key],
}));

/** A party's seats across both councils, keyed by party slug. */
export type PartyResult = {
  /** Internal identity, used to join rows. Positional, so never put in a URL. */
  key: string;
  /** Readable slug the URLs use, shared with the candidate pages. */
  urlSlug: string;
  party: string;
  partyName: string;
  partySlug: string | null;
  profileSlug: string | null;
  independent: boolean;
  seats: number;
  byBody: Partial<Record<Body, number>>;
  /** Region slugs where the party took at least one seat. */
  regions: string[];
  color: string;
};

/** Party identity key; independents are pooled under one key. */
const keyOf = (row: {
  independent: boolean;
  party_slug: string | null;
  party: string;
}) => (row.independent ? "independent" : (row.party_slug ?? row.party));

function buildPartyResults(): PartyResult[] {
  const acc = new Map<string, PartyResult>();
  for (const { key: body, data } of resultBodies) {
    for (const region of data.regions) {
      for (const won of region.won) {
        const key = keyOf(won);
        let entry = acc.get(key);
        if (!entry) {
          const candidateParty = won.party_slug
            ? partyBySlug.get(won.party_slug)
            : undefined;
          entry = {
            key,
            urlSlug:
              won.independent || !candidateParty
                ? "independent"
                : partyUrlSlug(candidateParty),
            party: won.independent ? "Independent" : won.party,
            partyName: won.independent
              ? "Independents"
              : (won.party_name_en ?? won.party),
            partySlug: won.independent ? null : won.party_slug,
            profileSlug: won.independent ? null : won.profile_slug,
            independent: won.independent,
            seats: 0,
            byBody: {},
            regions: [],
            color: OTHER_COLOR,
          };
          acc.set(key, entry);
        }
        entry.seats += won.seats;
        entry.byBody[body] = (entry.byBody[body] ?? 0) + won.seats;
        if (!entry.regions.includes(region.region_slug)) {
          entry.regions.push(region.region_slug);
        }
      }
    }
  }

  const ranked = Array.from(acc.values()).sort(
    (a, b) => b.seats - a.seats || a.partyName.localeCompare(b.partyName),
  );
  for (const party of ranked) {
    party.color = party === ranked[0] ? LEADER_COLOR : CHALLENGER_COLOR;
  }
  return ranked;
}

export const partyResults: PartyResult[] = buildPartyResults();

export const partyResultByKey = new Map(partyResults.map((p) => [p.key, p]));

export const partyResultByUrlSlug = new Map(
  partyResults.map((p) => [p.urlSlug, p]),
);

/** The address of a party's results page. */
export const partyResultHref = (p: PartyResult) =>
  `/results/party/${p.urlSlug}`;

// An independent's rows carry the candidate list's "Independent" party slug,
// which has to alias onto the pooled entry.
const byAnySlug = new Map<string, PartyResult>();
for (const p of partyResults) byAnySlug.set(p.key, p);
for (const { data } of resultBodies) {
  for (const region of data.regions) {
    for (const won of region.won) {
      const entry = partyResultByKey.get(keyOf(won));
      if (entry && won.party_slug) byAnySlug.set(won.party_slug, entry);
    }
  }
}

/** The party behind a row, whether it names a party slug or a pooled key. */
export const partyOfSlug = (slug: string | null | undefined) =>
  slug ? (byAnySlug.get(slug) ?? null) : null;

/** The party holding the most seats nationally. */
export const leadingParty: PartyResult = partyResults[0];

/** Winner of each constituency, keyed by constituency slug. */
export function winnersByConstituency(body: Body): Map<string, PartyResult> {
  const out = new Map<string, PartyResult>();
  for (const row of resultsElected[body]) {
    if (!row.constituency_slug) continue;
    const key = row.party_slug ?? row.party;
    const party = key ? partyResultByKey.get(key) : undefined;
    if (party) out.set(row.constituency_slug, party);
  }
  return out;
}

/** What the map paints for one seat. */
export type SeatOutcome = "leader" | "challenger" | "unknown";

export function seatOutcomes(body: Body): Record<string, SeatOutcome> {
  const winners = winnersByConstituency(body);
  const out: Record<string, SeatOutcome> = {};
  for (const c of candidateConstituencies(body)) {
    const winner = winners.get(c.slug);
    out[c.slug] = !winner
      ? "unknown"
      : winner.key === leadingParty.key
        ? "leader"
        : "challenger";
  }
  return out;
}

// --- The chamber, as seats ---------------------------------------------------

/** One block of the seat grid: a party and the tiles it holds in a chamber. */
export type SeatBlock = {
  party: string;
  seats: number;
  color: string;
  href: string | null;
  incumbent: boolean;
};

/** Every seat in a chamber, grouped by who holds it, largest holding first. */
export function seatBlocks(body: Body): SeatBlock[] {
  const holders = partyResults
    .filter((p) => (p.byBody[body] ?? 0) > 0)
    .sort((a, b) => (b.byBody[body] ?? 0) - (a.byBody[body] ?? 0));

  let hue = 0;
  const blocks: SeatBlock[] = [];
  let pooled = 0;

  for (const p of holders) {
    const seats = p.byBody[body] ?? 0;
    const incumbent = p.key === leadingParty.key;
    let color: string;
    if (incumbent) color = LEADER_COLOR;
    else if (p.independent) color = INDEPENDENT_COLOR;
    else if (hue < SEAT_HUES.length) color = SEAT_HUES[hue++];
    else {
      pooled += seats;
      continue;
    }
    blocks.push({
      party: p.partyName,
      seats,
      color,
      href: partyResultHref(p),
      incumbent,
    });
  }

  if (pooled > 0) {
    blocks.push({
      party: `${holders.length - blocks.length} smaller parties`,
      seats: pooled,
      color: OTHER_COLOR,
      href: null,
      incumbent: false,
    });
  }
  return blocks;
}

/** Seat outcomes from one party's point of view: their seats highlighted. */
export function seatOutcomesFor(
  body: Body,
  partyKey: string,
): Record<string, SeatOutcome> {
  const winners = winnersByConstituency(body);
  const out: Record<string, SeatOutcome> = {};
  for (const c of candidateConstituencies(body)) {
    const winner = winners.get(c.slug);
    out[c.slug] = !winner
      ? "unknown"
      : winner.key === partyKey
        ? "challenger" // the highlighted state; "challenger" is the gold slot
        : "leader";
  }
  return out;
}

// --- How the seats were actually won ---------------------------------------

export type Race = {
  constituencySlug: string;
  constituency: string;
  regionSlug: string;
  body: Body;
  winner: string;
  winnerParty: PartyResult | null;
  votes: number;
  totalVotes: number;
  /** The winner's share of the votes cast in the seat, 0-100. */
  share: number;
  /** Seats this constituency returned (1 for HoPR; RC seats are multi-member). */
  seats: number;
  /** Points between the last candidate elected and the first to miss a seat.
   * In a multi-member seat first and second can both be elected, so the race
   * is at that boundary. Null wherever the boundary cannot be trusted. */
  margin: number | null;
  /** The same gap in raw votes. */
  marginVotes: number | null;
  /** The pair the margin measures: who took the final seat, who missed it. */
  marginWinner: string | null;
  marginWinnerParty: PartyResult | null;
  marginLoser: string | null;
  candidates: number;
};

/** Every seat whose votes are published, reconstructed as a race. */
export function races(body: Body): Race[] {
  if (!hasVotes(body)) return [];
  // A margin is published only where the vote sheet's elected flags account
  // for every seat the elected list awards; otherwise the boundary could sit
  // between two winners.
  const listedSeats = new Map<string, number>();
  for (const row of resultsElected?.[body] ?? []) {
    if (row.constituency_slug)
      listedSeats.set(
        row.constituency_slug,
        (listedSeats.get(row.constituency_slug) ?? 0) + 1,
      );
  }
  const out: Race[] = [];
  for (const region of resultsSeats[body].regions) {
    const rows = votesFor(region.region_slug, body).filter(
      (r) => r.constituency_slug && r.votes !== null,
    );
    const byConstituency = new Map<string, VoteRow[]>();
    for (const r of rows) {
      const list = byConstituency.get(r.constituency_slug!) ?? [];
      list.push(r);
      byConstituency.set(r.constituency_slug!, list);
    }
    for (const [slug, list] of Array.from(byConstituency)) {
      list.sort((a, b) => (b.votes ?? 0) - (a.votes ?? 0));
      const total = list.reduce((n, r) => n + (r.votes ?? 0), 0);
      if (total === 0) continue;
      const first = list[0];
      const partyOf = (r?: VoteRow) => partyOfSlug(r?.party_slug);

      const elected = list.filter((r) => r.elected);
      const missed = list.filter((r) => !r.elected);
      const lastIn = elected[elected.length - 1];
      const firstOut = missed[0];
      const gap =
        lastIn?.votes != null && firstOut?.votes != null
          ? lastIn.votes - firstOut.votes
          : null;
      const measured =
        gap !== null && gap >= 0 && listedSeats.get(slug) === elected.length;

      out.push({
        constituencySlug: slug,
        constituency: first.constituency,
        regionSlug: region.region_slug,
        body,
        winner: first.candidate,
        winnerParty: partyOf(first),
        votes: first.votes ?? 0,
        totalVotes: total,
        share: ((first.votes ?? 0) / total) * 100,
        seats: elected.length,
        margin: measured ? ((gap as number) / total) * 100 : null,
        marginVotes: measured ? gap : null,
        marginWinner: measured ? lastIn.candidate : null,
        marginWinnerParty: measured ? partyOf(lastIn) : null,
        marginLoser: measured ? firstOut.candidate : null,
        candidates: list.length,
      });
    }
  }
  return out;
}

/** One dot per seat for the strip plot. Tuples, because this ships to the
 * browser as an attribute on the page. */
export type SeatDot = [
  share: number,
  incumbent: 0 | 1,
  seat: string,
  winner: string,
  party: string,
  slug: string,
];

export function seatDots(all: Race[]): SeatDot[] {
  return all.map((r) => [
    Math.round(r.share * 10) / 10,
    r.winnerParty?.key === leadingParty.key ? 1 : 0,
    r.constituency,
    r.winner,
    r.winnerParty?.partyName ?? "Not matched",
    r.constituencySlug,
  ]);
}

// --- Who the elected members are --------------------------------------------

export type ElectedDemographics = {
  total: number;
  /** Members matched to a candidate registration, which is where gender and
   * disability come from. */
  matched: number;
  women: number;
  men: number;
  disabled: number;
};

/** Gender and disability of the elected members, joined from their candidate
 * registrations by candidate id. */
export function electedDemographics(body: Body): ElectedDemographics {
  const rows = resultsElected?.[body] ?? [];
  const out: ElectedDemographics = {
    total: rows.length,
    matched: 0,
    women: 0,
    men: 0,
    disabled: 0,
  };

  const byRegion = new Map<string, ElectedRow[]>();
  for (const row of rows) {
    if (!row.candidate_id) continue;
    const list = byRegion.get(row.region_slug) ?? [];
    list.push(row);
    byRegion.set(row.region_slug, list);
  }

  for (const [regionSlug, list] of Array.from(byRegion)) {
    const byId = new Map(
      loadCandidates(regionSlug, body).map((c) => [c.candidate_id, c]),
    );
    for (const row of list) {
      const cand = byId.get(row.candidate_id!);
      if (!cand) continue;
      out.matched += 1;
      if (cand.gender === "Female") out.women += 1;
      else if (cand.gender === "Male") out.men += 1;
      if (cand.disability) out.disabled += 1;
    }
  }
  return out;
}
