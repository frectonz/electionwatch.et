import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

// Makes the whole site agent-navigable: mirrors every source dataset the site
// uses into public/data/ at stable URLs, writes a machine-readable manifest.json, and
// generates an llms.txt entry point (https://llmstxt.org) that describes the
// project, the datasets and their schemas, and links to both the human pages
// and the raw JSON — plus the debate analyses and party position dossiers,
// which are the editorial summaries an LLM can reason over.

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(__dirname, "../..");
const CAND_SRC = path.join(REPO, "candidates/data/json");
const PS_SRC = path.join(REPO, "polling-stations/data/json");
const TRANS_SRC = path.join(REPO, "transcripts/data");
const SYMBOLS_SRC = path.join(REPO, "symbols/data");

const PUBLIC = path.resolve(__dirname, "../public");
const DATA_DEST = path.join(PUBLIC, "data");
const SITE = "https://electionwatch.et";

function readJSON<T>(file: string): T {
  return JSON.parse(fs.readFileSync(file, "utf-8")) as T;
}

// Recursively mirror a directory of JSON into public/data/, returning the list
// of files copied (as paths relative to DATA_DEST) so the manifest can list
// every fetchable URL.
function mirror(srcDir: string, destSubdir: string): string[] {
  const copied: string[] = [];
  const walk = (rel: string) => {
    const absSrc = path.join(srcDir, rel);
    for (const entry of fs.readdirSync(absSrc, { withFileTypes: true })) {
      const childRel = path.join(rel, entry.name);
      if (entry.isDirectory()) {
        walk(childRel);
      } else if (entry.name.endsWith(".json")) {
        const dest = path.join(DATA_DEST, destSubdir, childRel);
        fs.mkdirSync(path.dirname(dest), { recursive: true });
        fs.copyFileSync(path.join(srcDir, childRel), dest);
        copied.push(path.join(destSubdir, childRel));
      }
    }
  };
  walk("");
  return copied.sort();
}

type CandIndex = {
  total_candidates: number;
  party_count: number;
  region_count: number;
  hopr_constituency_count: number;
  rc_constituency_count: number;
  with_disability: number;
  by_body: { hopr: number; rc: number };
  by_gender: Record<string, number>;
  by_education: Record<string, number>;
};
type PsIndex = {
  total_stations: number;
  with_coordinates: number;
  without_coordinates: number;
  region_count: number;
};

const num = (n: number) => n.toLocaleString("en-US");

const SOURCE_LABEL: Record<string, string> = {
  etv_nebe: "ETV / NEBE",
  fana_medrek: "Fana Medrek",
};

type DebateMeta = {
  video_id: string;
  source: string;
  upload_date: string;
  youtube_url: string;
  duration_seconds: number;
  title: string;
  parties: { name: string; slug: string }[];
};
type TranscriptSegment = { text: string; start: number; duration: number };
type PositionsFile = { slug: string; name: string; positions: unknown[] };

// mm:ss (or h:mm:ss) from a number of seconds.
const clock = (t: number): string => {
  const s = Math.max(0, Math.floor(t));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${m}:${pad(sec)}`;
};
const hm = (seconds: number): string => {
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
};

// Render a debate's caption segments into a clean Markdown transcript an LLM (or
// a person) can read top to bottom: a header of context, then the text in
// timestamped paragraphs (~30s each) for navigation back to the video.
function renderTranscript(
  meta: DebateMeta,
  segments: TranscriptSegment[],
  links: { meta: string; analysis: string; json: string },
): string {
  const out: string[] = [
    `# ${meta.title}`,
    "",
    `- **Broadcaster:** ${SOURCE_LABEL[meta.source] ?? meta.source}`,
    `- **Date:** ${meta.upload_date}`,
    `- **Duration:** ${hm(meta.duration_seconds)}`,
    `- **Language:** Amharic`,
    `- **YouTube:** ${meta.youtube_url}`,
    `- **Participating parties:** ${meta.parties.map((p) => p.name).join(", ")}`,
    `- **Structured data:** [metadata](${links.meta}) · [question-by-question analysis](${links.analysis}) · [raw caption JSON](${links.json})`,
    "",
    "> Auto-generated from the broadcast captions. Timestamps are mm:ss (or h:mm:ss) from the start of the video.",
    "",
    "---",
    "",
  ];
  let start: number | null = null;
  let buf: string[] = [];
  const flush = () => {
    if (buf.length && start !== null) {
      out.push(
        `**[${clock(start)}]** ${buf.join(" ").replace(/\s+/g, " ").trim()}`,
        "",
      );
    }
    buf = [];
    start = null;
  };
  for (const seg of segments) {
    if (start === null) start = seg.start;
    buf.push(seg.text);
    if (seg.start - start >= 30) flush();
  }
  flush();
  return out.join("\n") + "\n";
}

export function buildLlms() {
  if (!fs.existsSync(CAND_SRC) || !fs.existsSync(TRANS_SRC)) {
    console.warn("[llms] source datasets not found, skipping");
    return;
  }

  // Clear only the subdirs this script owns, so renamed/removed source files
  // don't linger (the polling-stations-map/ dir is written by another
  // integration — leave it alone).
  for (const sub of [
    "candidates",
    "polling-stations",
    "debates",
    "party-positions",
  ]) {
    fs.rmSync(path.join(DATA_DEST, sub), { recursive: true, force: true });
  }

  // 1. Mirror the raw datasets into public/data/ at stable URLs. The transcripts
  // source holds two distinct datasets — the debate broadcasts (under etv_nebe/
  // and fana_medrek/) and the per-party position dossiers (positions/) — so they
  // are mirrored, and listed below, separately.
  const candFiles = mirror(CAND_SRC, "candidates");
  const psFiles = mirror(PS_SRC, "polling-stations");
  const debateFiles = [
    ...mirror(path.join(TRANS_SRC, "etv_nebe"), "debates/etv_nebe"),
    ...mirror(path.join(TRANS_SRC, "fana_medrek"), "debates/fana_medrek"),
  ].sort();
  const positionFiles = mirror(
    path.join(TRANS_SRC, "positions"),
    "party-positions",
  );
  // The shared party-name registry, served alongside the position dossiers.
  fs.copyFileSync(
    path.join(TRANS_SRC, "parties.json"),
    path.join(DATA_DEST, "party-positions", "parties.json"),
  );
  positionFiles.push(path.join("party-positions", "parties.json"));
  positionFiles.sort();

  // public/data/<rel> is served at /data/<rel>.
  const url = (rel: string) => `${SITE}/data/${rel.split(path.sep).join("/")}`;

  // English party names, for labelling symbols and positions. The debate
  // registry carries English names; fall back to the candidate parties list
  // (keyed by profile_slug).
  const transRegistry = readJSON<Record<string, { name: string }>>(
    path.join(TRANS_SRC, "parties.json"),
  );
  const candParties = readJSON<{ profile_slug?: string; name_en: string }[]>(
    path.join(CAND_SRC, "parties.json"),
  );
  const englishName = new Map<string, string>();
  for (const [slug, info] of Object.entries(transRegistry)) {
    englishName.set(slug, info.name);
  }
  for (const cp of candParties) {
    if (cp.profile_slug && !englishName.has(cp.profile_slug)) {
      englishName.set(cp.profile_slug, cp.name_en);
    }
  }

  // Party ballot symbols: the PNGs are served at /symbols/<file> (synced by
  // sync-symbols.ts). Publish an index joining each party to its English name,
  // its ballot symbol's Amharic name, and the image URL.
  const symbolsRaw = readJSON<
    { slug: string; symbol_name: string; image: string }[]
  >(path.join(SYMBOLS_SRC, "symbols.json"));
  const symbols = symbolsRaw.map((s) => ({
    slug: s.slug,
    party_name: englishName.get(s.slug) ?? null,
    symbol_name: s.symbol_name,
    image: `${SITE}/symbols/${s.image}`,
    source: "NEBE ballot symbol list",
  }));
  fs.mkdirSync(DATA_DEST, { recursive: true });
  fs.writeFileSync(
    path.join(DATA_DEST, "symbols.json"),
    JSON.stringify(symbols, null, 2),
  );
  const symbolBySlug = new Map(symbols.map((s) => [s.slug, s.image]));

  // Debates: a self-describing index plus a clean Markdown transcript per
  // broadcast (written alongside the raw caption JSON).
  const debateIndex: Record<string, unknown>[] = [];
  for (const source of Object.keys(SOURCE_LABEL)) {
    const dir = path.join(TRANS_SRC, source);
    if (!fs.existsSync(dir)) continue;
    for (const file of fs
      .readdirSync(dir)
      .filter((f) => f.endsWith(".meta.json"))
      .sort()) {
      const base = file.replace(/\.meta\.json$/, "");
      const meta = readJSON<DebateMeta>(path.join(dir, file));
      const metaUrl = url(`debates/${source}/${base}.meta.json`);
      const analysisUrl = url(`debates/${source}/${base}.analysis.json`);
      const jsonUrl = url(`debates/${source}/${base}.json`);
      let mdUrl: string | null = null;
      const transcriptPath = path.join(dir, `${base}.json`);
      if (fs.existsSync(transcriptPath)) {
        const segments = readJSON<TranscriptSegment[]>(transcriptPath);
        fs.writeFileSync(
          path.join(DATA_DEST, "debates", source, `${base}.md`),
          renderTranscript(meta, segments, {
            meta: metaUrl,
            analysis: analysisUrl,
            json: jsonUrl,
          }),
        );
        mdUrl = url(`debates/${source}/${base}.md`);
      }
      debateIndex.push({
        video_id: meta.video_id,
        title: meta.title,
        broadcaster: SOURCE_LABEL[source],
        date: meta.upload_date,
        language: "Amharic",
        duration_seconds: meta.duration_seconds,
        youtube_url: meta.youtube_url,
        participating_parties: meta.parties,
        transcript_markdown: mdUrl,
        transcript_json: jsonUrl,
        analysis: analysisUrl,
        metadata: metaUrl,
      });
    }
  }
  debateIndex.sort((a, b) => (String(a.date) < String(b.date) ? 1 : -1));
  fs.writeFileSync(
    path.join(DATA_DEST, "debates", "index.json"),
    JSON.stringify(
      { count: debateIndex.length, debates: debateIndex },
      null,
      2,
    ),
  );

  // Party positions: a self-describing index — each dossier with its ballot
  // symbol and human profile page.
  const partyPositions = positionFiles
    .filter((rel) => rel.endsWith(".json") && !rel.endsWith("parties.json"))
    .map((rel) => {
      const pf = readJSON<PositionsFile>(path.join(DATA_DEST, rel));
      return {
        slug: pf.slug,
        name: pf.name,
        positions: pf.positions.length,
        json: url(rel),
        symbol: symbolBySlug.get(pf.slug) ?? null,
        profile: `${SITE}/parties/${pf.slug}`,
      };
    })
    .sort((a, b) => a.name.localeCompare(b.name));
  fs.writeFileSync(
    path.join(DATA_DEST, "party-positions", "index.json"),
    JSON.stringify(
      {
        registry: url("party-positions/parties.json"),
        count: partyPositions.length,
        parties: partyPositions,
      },
      null,
      2,
    ),
  );

  // The compact polling-station map dataset is generated by the
  // polling-station-map integration (build-ps-points.ts), which runs before
  // this one. List its files so the manifest covers everything the site uses.
  const mapFiles: string[] = [];
  if (fs.existsSync(path.join(DATA_DEST, "polling-stations-map.json"))) {
    mapFiles.push("polling-stations-map.json");
  }
  const mapDir = path.join(DATA_DEST, "polling-stations-map");
  if (fs.existsSync(mapDir)) {
    for (const f of fs.readdirSync(mapDir).sort()) {
      mapFiles.push(path.join("polling-stations-map", f));
    }
  }

  const candIdx = readJSON<CandIndex>(path.join(CAND_SRC, "index.json"));
  const psIdx = readJSON<PsIndex>(path.join(PS_SRC, "index.json"));
  const debateCount = debateFiles.filter((f) =>
    f.endsWith(".meta.json"),
  ).length;
  const positionCount = partyPositions.length;

  // 2. Machine-readable manifest: every dataset, its stats, and its files.
  const manifest = {
    name: "electionwatch.et",
    description:
      "Open, cross-linked datasets on Ethiopia's 7th General Election.",
    site: SITE,
    license: "Public material, structured for reuse; verify against sources.",
    generated_at: new Date().toISOString().slice(0, 10),
    datasets: [
      {
        id: "debates",
        title: "Debate broadcasts",
        records: debateCount,
        recordsLabel: "broadcasts analysed",
        index: url("debates/index.json"),
        notes:
          "Each broadcast also has a clean Markdown transcript (…/<id>.md), linked from index.json as transcript_markdown.",
        files: debateFiles.map(url),
      },
      {
        id: "party-positions",
        title: "Party positions",
        records: positionCount,
        recordsLabel: "party position dossiers",
        index: url("party-positions/index.json"),
        registry: url("party-positions/parties.json"),
        files: positionFiles.map(url),
      },
      {
        id: "polling-stations",
        title: "Polling stations",
        records: psIdx.total_stations,
        recordsLabel: "polling stations",
        index: url("polling-stations/index.json"),
        files: psFiles.map(url),
        // Compact GPS-located subset the interactive map fetches at runtime.
        map: mapFiles.map(url),
        notes: `${num(psIdx.with_coordinates)} of ${num(
          psIdx.total_stations,
        )} stations have NEBE-published GPS coordinates.`,
      },
      {
        id: "candidates",
        title: "Candidates",
        records: candIdx.total_candidates,
        recordsLabel: "candidates",
        index: url("candidates/index.json"),
        files: candFiles.map(url),
      },
      {
        id: "symbols",
        title: "Party ballot symbols",
        records: symbols.length,
        recordsLabel: "party symbols",
        index: url("symbols.json"),
        // Image URLs live under /symbols/, not /data/.
        files: symbols.map((s) => s.image),
      },
    ],
  };
  fs.mkdirSync(DATA_DEST, { recursive: true });
  fs.writeFileSync(
    path.join(DATA_DEST, "manifest.json"),
    JSON.stringify(manifest, null, 2),
  );

  // 3. The llms.txt entry point.
  fs.writeFileSync(
    path.join(PUBLIC, "llms.txt"),
    renderLlmsTxt(candIdx, psIdx, debateCount, positionCount),
  );

  const total =
    candFiles.length +
    psFiles.length +
    debateFiles.length +
    positionFiles.length +
    1; // symbols.json
  console.log(
    `[llms] mirrored ${total} JSON files -> public/data/ + manifest.json + llms.txt`,
  );
}

function renderLlmsTxt(
  c: CandIndex,
  p: PsIndex,
  debates: number,
  positions: number,
): string {
  const women = c.by_gender.Female ?? 0;
  const womenPct = Math.round((women / c.total_candidates) * 100);
  const coordPct = Math.round((p.with_coordinates / p.total_stations) * 100);

  return `# electionwatch.et

> An independent, open-data portal for Ethiopia's 7th General Election. It takes
> the public record — the National Election Board's (NEBE) candidate lists and
> polling-station registries, and the official party debate broadcasts — and
> turns it into structured, cross-linked JSON datasets that are easy to query,
> compare, and cite. This file is the entry point for loading the site and its
> data into an LLM so you can ask your own questions and run your own analysis.

## How to use this with an LLM

Every dataset below is published as plain JSON at a stable URL. Fetch the
\`index.json\` for an overview, then the per-region or per-party files for the
full records. The machine-readable manifest of every file lives at
${SITE}/data/manifest.json. All records are derived from public sources; each is
linked back to its origin so you can verify it. Where data is extracted from
PDFs or summarized automatically it may contain errors — check the linked source
before drawing conclusions.

## Key figures

- ${num(c.total_candidates)} candidates cleared across ${num(c.region_count)} regions and ${num(c.party_count)} parties (${num(c.by_body.hopr)} for the federal House of People's Representatives, ${num(c.by_body.rc)} for the Regional Councils).
- ${num(women)} candidates (${womenPct}%) are women; ${num(c.with_disability)} are candidates with a disability.
- ${num(p.total_stations)} registered polling stations; ${num(p.with_coordinates)} (${coordPct}%) carry NEBE-published GPS coordinates.
- ${num(debates)} official debate broadcasts analysed question-by-question, distilled into ${num(positions)} per-party position dossiers.

## Candidates

Every candidate NEBE cleared, by region, constituency, and party, for the two
ballots (HoPR = federal House of People's Representatives, RC = Regional
Council). Source: https://nebe.org.et/en/candidate-list

- [Overview & breakdowns](${SITE}/data/candidates/index.json): totals by body, gender, education, region, and party.
- [Parties](${SITE}/data/candidates/parties.json): each party's candidate counts (\`name\`, \`name_en\`, \`candidates\`, \`hopr\`, \`rc\`, \`slug\`, \`profile_slug\`).
- [Regions](${SITE}/data/candidates/regions.json) and [Constituencies](${SITE}/data/candidates/constituencies.json): \`{ hopr: [...], rc: [...] }\`, each constituency with candidate/party counts and the polling-station codes voted there.
- [Station links](${SITE}/data/candidates/station_links.json): maps polling-station constituency codes to the candidate constituency voted on there.
- Per-region records under \`${SITE}/data/candidates/candidates/<region>_<body>.json\` (e.g. \`oromia_hopr.json\`). Each record: \`region\`, \`constituency\`, \`candidate_id\`, \`full_name\`, \`gender\`, \`disability\`, \`party\`, \`education\`, \`body\`. Names are in Amharic.
- Human view: ${SITE}/data/candidates

## Polling stations

Every registered polling station, structured by region, zone, woreda, kebele,
and electoral constituency, with coordinates where NEBE published them. Source:
https://nebe.org.et/en/List_of_polling_stations

- [Overview](${SITE}/data/polling-stations/index.json), [Regions](${SITE}/data/polling-stations/regions.json), [Constituencies](${SITE}/data/polling-stations/constituencies.json).
- Per-region records under \`${SITE}/data/polling-stations/stations/<region>_<digital|manual>.json\`. Each record: location codes/names down to kebele, \`hopr_constituency_code\`/\`rc_constituency_code\` (join keys), \`polling_station_code\`, \`name\`, \`latitude\`/\`longitude\` (null where NEBE left them blank), \`registration_type\`.
- Map of GPS-located stations (compact): ${SITE}/data/polling-stations-map.json (+ per-region files under \`/data/polling-stations-map/<region>.json\`).
- Human view: ${SITE}/data/polling-stations

## Debates

Question-by-question analyses of every official debate broadcast (ETV/NEBE and
Fana Medrek). The analysis files are the editorial summaries: each claim and key
point links to the exact YouTube timestamp where it was spoken. Source:
${SITE}/data/debates

- **Start here:** [${SITE}/data/debates/index.json](${SITE}/data/debates/index.json) — every broadcast with its date, broadcaster, title, participating parties, and links to its metadata, analysis, raw captions, and a clean Markdown transcript.
- Per-debate files under \`${SITE}/data/debates/etv_nebe/\` and \`${SITE}/data/debates/fana_medrek/\`, each broadcast as:
  - \`<id>.md\` — a clean, readable Markdown transcript (header of context + timestamped paragraphs). Best for reading.
  - \`<id>.meta.json\` — title, source, upload date, duration, YouTube URL, participating parties.
  - \`<id>.analysis.json\` — \`overall_topic\` and \`questions[]\`, each with \`asker\`, \`topic\`, \`question\`, and per-party \`answers[]\` carrying a \`summary\`, \`key_points[]\`, and timestamped \`citations[]\`.
  - \`<id>.json\` — the raw caption segments (\`text\`, \`start\`, \`duration\`).
- Human view: ${SITE}/data/debates

## Party positions

Consolidated, citable position dossiers per party, aggregated across every
debate appearance into one file. These are the editorial summaries of where each
party stands. Source: ${SITE}/parties

- **Start here:** [${SITE}/data/party-positions/index.json](${SITE}/data/party-positions/index.json) — each party with its name, position count, dossier URL, ballot symbol, and profile page.
- Position dossiers under \`${SITE}/data/party-positions/<party-slug>.json\`: each \`{ topic, position, citations[] }\`, where every citation links to the moment in a debate it was stated.
- Party registry (slug → name): ${SITE}/data/party-positions/parties.json
- Human view: ${SITE}/parties

## Party symbols

The ballot symbol assigned to each party, as rendered from the NEBE ballot.

- [Symbol index](${SITE}/data/symbols.json): an array of \`{ slug, party_name, symbol_name, image, source }\`, where \`party_name\` is the party's English name (where known), \`symbol_name\` is the symbol's Amharic name, and \`image\` is the full URL of its PNG (served under \`${SITE}/symbols/\`). Join \`slug\` to a party's \`profile_slug\` (candidates) or position-file slug.

## About

- Methodology, sources, and disclaimer: ${SITE}/about
- All datasets, with record counts and sources: ${SITE}/data
- Open source: https://github.com/frectonz/electionwatch.et

This is an independent, unofficial project. It is not affiliated with or
endorsed by the Ethiopian government, NEBE, or any political party.
`;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  buildLlms();
}
