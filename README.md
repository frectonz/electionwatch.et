# electionwatch.et

An independent civic project publishing open data for Ethiopia's 7th General Election: party debate positions, the full candidate lists, and the polling stations where people vote.

**Live at [electionwatch.et](https://electionwatch.et)**

## Data

Everything comes from material published by the National Election Board of Ethiopia (NEBE). The repository is split into the data pipelines that prepare it and the website that presents it:

- `transcripts/` — official party debates: transcribed, then analysed into per-party positions with citations back to the source video.
- `candidates/` — the full HoPR and Regional Council candidate lists, parsed from NEBE's PDFs and cross-linked to parties and polling stations.
- `polling-stations/` — every registered polling station, with NEBE-published GPS coordinates where available.
- `symbols/` — the ballot symbols matched to each party.
- `website/` — the Astro site that renders all of the above.

Each pipeline preprocesses its source into website-ready JSON; the website does no heavy joining at request time.

## Development

```bash
cd website
pnpm install
pnpm dev
```

## Build

```bash
cd website
pnpm build
pnpm preview
```

## Disclaimer

This is an independent, unofficial, open-source project. It is not affiliated with or endorsed by the Ethiopian government, the National Election Board of Ethiopia, or any political party. Data is provided as-is for informational purposes.
