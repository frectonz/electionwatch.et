"""Analyze Ethiopian-election debate transcripts with Gemini.

Per-transcript pass: extracts each question + each party's answer, in English,
with citations back to the source segments. Synthesis pass: consolidates each
party's policy positions across all transcripts, preserving citations.

Usage:
    uv run python analyze.py --api-key KEY
    GEMINI_API_KEY=... uv run python analyze.py
    uv run python analyze.py --only BPDQbsjWZ94 --force
    uv run python analyze.py --only-synthesis
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

load_dotenv(dotenv_path=Path(__file__).parent / ".env")


@dataclass
class Stats:
    input_tokens: int = 0
    output_tokens: int = 0

    def record(self, tin: int, tout: int) -> None:
        self.input_tokens += tin
        self.output_tokens += tout


STATS = Stats()

DATA_DIR = Path(__file__).parent / "data"
PARTIES_JSON = DATA_DIR / "parties.json"
POSITIONS_DIR = DATA_DIR / "positions"
SOURCES = ("etv_nebe", "fana_medrek")


class Span(BaseModel):
    start: int = Field(description="0-based inclusive start segment index")
    end: int = Field(description="0-based inclusive end segment index (>= start)")


SPANS_DESC = (
    "One or more inclusive [start, end] segment ranges supporting this content. "
    "Prefer a single tight range. Use multiple ranges only if the supporting "
    "evidence is genuinely non-contiguous (e.g. the speaker returns to a point later)."
)


class KeyPoint(BaseModel):
    point: str = Field(description="A single specific claim, promise, or position")
    spans: list[Span] = Field(
        description=f"Spans backing THIS specific claim. {SPANS_DESC}"
    )


class Answer(BaseModel):
    party_slug: str = Field(description="kebab-case slug from the parties registry")
    summary: str = Field(description="Faithful English summary of the response")
    key_points: list[KeyPoint]
    spans: list[Span] = Field(
        description=f"Spans covering this party's full answer for orientation. {SPANS_DESC}"
    )


class Question(BaseModel):
    asker: str = Field(description='"moderator", "audience", or a party slug')
    topic: str = Field(description="Short topic label, e.g. 'Land tenure'")
    question: str = Field(description="Faithful English summary of the question")
    spans: list[Span] = Field(
        description=f"Spans where the question was posed. {SPANS_DESC}"
    )
    answers: list[Answer]


class TranscriptAnalysis(BaseModel):
    overall_topic: str
    questions: list[Question]


class PolicyCitation(BaseModel):
    video_id: str = Field(
        description="video_id of the transcript this evidence comes from"
    )
    excerpt: str = Field(description="Short English paraphrase of the cited statement")
    spans: list[Span] = Field(
        description="MUST be copied verbatim from a per-transcript answer's or key-point's spans. Never invented."
    )


class PolicyPosition(BaseModel):
    topic: str
    position: str
    citations: list[PolicyCitation] = Field(
        description="At least one citation per position"
    )


class PartyPositionsResponse(BaseModel):
    positions: list[PolicyPosition]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def find_transcripts() -> list[Path]:
    return sorted(
        p
        for src in SOURCES
        for p in (DATA_DIR / src).glob("[0-9]*.json")
        if not p.name.endswith((".meta.json", ".analysis.json"))
    )


def video_id_of(transcript: Path) -> str:
    # Split on the FIRST '-' so video_ids that themselves start with '-' survive.
    return transcript.stem.split("-", 1)[1]


def meta_path(transcript: Path) -> Path:
    return transcript.with_name(transcript.stem + ".meta.json")


def analysis_path(transcript: Path) -> Path:
    return transcript.with_name(transcript.stem + ".analysis.json")


def transcript_path_for(video_id: str, source: str, upload_date: str) -> Path:
    return DATA_DIR / source / f"{upload_date.replace('-', '')}-{video_id}.json"


def indexed_segments(transcript: Path) -> list[dict]:
    return [
        {"index": i, "start": s["start"], "duration": s["duration"], "text": s["text"]}
        for i, s in enumerate(load_json(transcript))
    ]


def resolve_spans(segments: list[dict], spans: list[Span], video_id: str) -> list[dict]:
    """Convert raw Spans into time-stamped citations, dropping spans with no valid indices."""
    n = len(segments)
    out = []
    for sp in spans:
        if sp.start >= n or sp.end < 0:
            continue
        s = max(0, min(sp.start, n - 1))
        e = max(s, min(sp.end, n - 1))
        first, last = segments[s], segments[e]
        start_s = first["start"]
        end_s = last["start"] + last["duration"]
        out.append(
            {
                "start_index": s,
                "end_index": e,
                "start": round(start_s, 2),
                "end": round(end_s, 2),
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}&t={round(start_s)}s",
                "embed_url": f"https://www.youtube.com/embed/{video_id}?start={round(start_s)}&end={round(end_s) + 1}",
            }
        )
    return out


def warn(msg: str) -> None:
    print(f"  WARN: {msg}", file=sys.stderr)


def party_registry_block(parties: dict) -> str:
    return "\n".join(f"  {slug}: {info['name']}" for slug, info in parties.items())


def per_transcript_prompt(meta: dict, parties: dict, segments: list[dict]) -> str:
    participating = ", ".join(p["slug"] for p in meta.get("parties", []))
    return f"""You are analyzing an Amharic political-debate transcript from Ethiopia's 7th national election.

CONTEXT
  Title: {meta.get("title", "")}
  Source program: {meta["source"]}
  Air date: {meta["upload_date"]}
  Participating party slugs (from this episode's metadata): {participating}

PARTY REGISTRY (slug -> display name; only use slugs from this list)
{party_registry_block(parties)}

TASK
  1. Identify each distinct question asked during the debate. Most come from the moderator(s); some may come from audience members or from one party to another.
  2. For each question, identify each participating party's response.
  3. Summarize the question and each response in clear, faithful English. Do not add policy claims that aren't stated by the speaker.
  4. Cite the transcript by segment index (0-based) so every claim links back to the source.

GROUNDING RULES (important — citations are how we avoid misrepresenting parties)
  - Only use slugs from the registry above. If a speaker cannot be matched to a party from this episode, skip their statement.
  - Every question, answer, AND key_point MUST include `spans` pointing to the specific segments where that exact content was spoken. Indices must exist in the transcript array — never invent them.
  - Each `Span` is an inclusive [start, end] index range. Prefer ONE tight span. Use MULTIPLE spans only when the supporting evidence is genuinely non-contiguous (e.g. the speaker returns to a point later in their turn).
  - Each key_point's spans should be NARROW — point at the 1–3 segments where that specific claim was actually said. Don't reuse the full answer range for every key_point. This is what lets a reader verify a single claim without re-reading the whole answer.
  - The answer-level `spans` should cover the party's full turn for orientation.
  - If a party did not answer a question, omit them from that question's answers. Do NOT fabricate an answer.
  - The `point` field of each key_point should be a specific factual claim or promise (e.g. "Pledges 500,000 affordable homes by 2030"), not a vague characterization.

TRANSCRIPT (JSON array of segments; each has index, start seconds, duration, Amharic text)
{json.dumps(segments, ensure_ascii=False)}
"""


def party_synthesis_prompt(slug: str, name: str, party_input: list[dict]) -> str:
    return f"""You are consolidating one Ethiopian political party's policy positions across the debates in which they participated.

PARTY
  Slug: {slug}
  Display name: {name}

INPUT
  An array of per-transcript items. Each contains a video_id and the questions where {name} answered, along with their summary, key_points, and grounded spans (segment-index ranges) in that transcript.

TASK
  Produce a list of {name}'s distinct policy positions across these debates.

GROUNDING RULES (critical)
  - Only attribute a position if it is supported by THIS party's own statements in the input. Do not invent positions.
  - Every position MUST have at least one citation. Each citation's `spans` MUST be copied verbatim from one of this party's answers OR key_points in the input. Never invent ranges or attribute statements to the wrong video_id.
  - Prefer the NARROWER spans (from key_points) over the wider answer-level spans when both are available — they support more precise UI links to the moment a claim was made.
  - Consolidate similar positions across transcripts into one entry with multiple citations (one per transcript that supports it).
  - Use coherent topic labels (e.g. "Economic policy", "Federalism and the constitution"). Reuse topics from the input questions when applicable.

INPUT (JSON)
{json.dumps(party_input, ensure_ascii=False)}
"""


def call_gemini(client, model: str, prompt: str, schema: type[BaseModel]):
    t0 = time.monotonic()
    with Progress(
        SpinnerColumn(),
        TextColumn(f"[bold blue]Gemini[/] ({model})"),
        TimeElapsedColumn(),
        transient=True,
    ) as progress:
        progress.add_task("", total=None)
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.1,
            ),
        )
    elapsed = time.monotonic() - t0
    if resp.parsed is None:
        raise RuntimeError(
            f"Gemini returned no parsed object; raw text: {(resp.text or '')[:500]}"
        )
    u = resp.usage_metadata
    if u is not None:
        tin, tout = u.prompt_token_count or 0, u.candidates_token_count or 0
        STATS.record(tin, tout)
        print(f"    {elapsed:.1f}s · {tin:,} in / {tout:,} out tokens")
    else:
        print(f"    {elapsed:.1f}s")
    return resp.parsed


def analyze_one(client, model: str, transcript: Path, parties: dict) -> dict:
    meta = load_json(meta_path(transcript))
    segments = indexed_segments(transcript)
    parsed: TranscriptAnalysis = call_gemini(
        client,
        model,
        per_transcript_prompt(meta, parties, segments),
        TranscriptAnalysis,
    )

    valid = set(parties)
    video_id = meta["video_id"]

    def build_answer(a: Answer) -> dict | None:
        if a.party_slug not in valid:
            warn(f"unknown slug '{a.party_slug}' in answer for {video_id}")
            return None
        return {
            "party_slug": a.party_slug,
            "summary": a.summary,
            "key_points": [
                {
                    "point": kp.point,
                    "citations": resolve_spans(segments, kp.spans, video_id),
                }
                for kp in a.key_points
            ],
            "citations": resolve_spans(segments, a.spans, video_id),
        }

    return {
        "video_id": video_id,
        "title": meta.get("title"),
        "source": meta["source"],
        "upload_date": meta["upload_date"],
        "youtube_url": meta["youtube_url"],
        "overall_topic": parsed.overall_topic,
        "questions": [
            {
                "asker": q.asker,
                "topic": q.topic,
                "question": q.question,
                "citations": resolve_spans(segments, q.spans, video_id),
                "answers": [a for a in (build_answer(a) for a in q.answers) if a],
            }
            for q in parsed.questions
        ],
    }


def _spans_from_citations(citations: list[dict]) -> list[dict]:
    """Project resolved citations back to bare {start, end} spans for synthesis input."""
    return [{"start": c["start_index"], "end": c["end_index"]} for c in citations]


def build_party_input(slug: str, analyses: list[dict]) -> list[dict]:
    """Filter all analyses to just questions where this party answered with valid citations."""
    out = []
    for a in analyses:
        relevant = []
        for q in a["questions"]:
            answers = []
            for ans in q["answers"]:
                if ans["party_slug"] != slug:
                    continue
                has_cite = bool(ans["citations"]) or any(
                    kp["citations"] for kp in ans["key_points"]
                )
                if not has_cite:
                    continue
                answers.append(
                    {
                        "summary": ans["summary"],
                        "key_points": [
                            {
                                "point": kp["point"],
                                "spans": _spans_from_citations(kp["citations"]),
                            }
                            for kp in ans["key_points"]
                            if kp["citations"]
                        ],
                        "spans": _spans_from_citations(ans["citations"]),
                    }
                )
            if answers:
                relevant.append(
                    {"topic": q["topic"], "question": q["question"], "answers": answers}
                )
        if relevant:
            out.append(
                {
                    "video_id": a["video_id"],
                    "title": a.get("title"),
                    "upload_date": a.get("upload_date"),
                    "questions": relevant,
                }
            )
    return out


def synthesize_party(
    client,
    model: str,
    slug: str,
    name: str,
    party_input: list[dict],
    seg_cache: dict[str, list[dict]],
) -> list[dict]:
    parsed: PartyPositionsResponse = call_gemini(
        client,
        model,
        party_synthesis_prompt(slug, name, party_input),
        PartyPositionsResponse,
    )

    def build_citation(c: PolicyCitation) -> dict | None:
        segs = seg_cache.get(c.video_id)
        if segs is None:
            warn(f"{slug}: synthesis cited unknown video_id '{c.video_id}'")
            return None
        spans = resolve_spans(segs, c.spans, c.video_id)
        if not spans:
            return None
        return {"video_id": c.video_id, "excerpt": c.excerpt, "spans": spans}

    positions = []
    for pos in parsed.positions:
        cits = [c for c in (build_citation(c) for c in pos.citations) if c]
        if cits:
            positions.append(
                {"topic": pos.topic, "position": pos.position, "citations": cits}
            )
    return positions


def print_totals(run_start: float) -> None:
    elapsed = time.monotonic() - run_start
    print(
        f"done in {elapsed:.1f}s · "
        f"{STATS.input_tokens:,} in / {STATS.output_tokens:,} out tokens"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--api-key",
        default=os.environ.get("GEMINI_API_KEY"),
        help="Gemini API key (or set GEMINI_API_KEY env var)",
    )
    ap.add_argument(
        "--model",
        default=os.environ.get("GEMINI_MODEL", "gemini-3.1-pro-preview"),
        help="Gemini model (default: gemini-3.1-pro-preview, or $GEMINI_MODEL)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Re-analyze even if <basename>.analysis.json exists",
    )
    ap.add_argument(
        "--no-synthesis",
        action="store_true",
        help="Skip the cross-transcript synthesis pass",
    )
    ap.add_argument(
        "--fail-fast",
        action="store_true",
        help="Exit on the first Gemini failure instead of warning and continuing",
    )
    ap.add_argument(
        "--skip",
        action="append",
        default=[],
        metavar="VIDEO_ID",
        help="Skip this video_id (repeatable)",
    )
    phase = ap.add_mutually_exclusive_group()
    phase.add_argument(
        "--only",
        help="Only process this video_id (also scopes synthesis to it)",
    )
    phase.add_argument(
        "--only-synthesis",
        action="store_true",
        help="Skip per-transcript analysis; only run synthesis from existing files",
    )
    args = ap.parse_args()

    if not args.api_key:
        sys.exit("Provide --api-key or set GEMINI_API_KEY env var.")

    client = genai.Client(
        api_key=args.api_key,
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(attempts=3, max_delay=10.0),
        ),
    )
    parties = load_json(PARTIES_JSON)
    paths = find_transcripts()
    run_start = time.monotonic()

    if not args.only_synthesis:
        skips = set(args.skip)
        to_do = [
            t
            for t in paths
            if (not args.only or args.only == video_id_of(t))
            and video_id_of(t) not in skips
            and (args.force or not analysis_path(t).exists())
        ]
        skipped = [
            t
            for t in paths
            if (not args.only or args.only == video_id_of(t))
            and video_id_of(t) not in skips
            and analysis_path(t).exists()
            and not args.force
        ]
        for t in skipped:
            print(f"skip {t.name} (analysis exists; --force to redo)")
        if to_do:
            print(f"model: {args.model} · {len(to_do)} transcript(s) to analyze")
        for i, transcript in enumerate(to_do, 1):
            print(f"[{i}/{len(to_do)}] {transcript.name}")
            try:
                analysis = analyze_one(client, args.model, transcript, parties)
            except Exception as e:
                if args.fail_fast:
                    sys.exit(f"failed {transcript.name}: {e}")
                warn(f"failed {transcript.name}: {e}")
                continue
            write_json(analysis_path(transcript), analysis)
            print(
                f"    wrote {analysis_path(transcript).name} ({len(analysis['questions'])} questions)"
            )

    if args.no_synthesis:
        print_totals(run_start)
        return

    analyses = [load_json(analysis_path(t)) for t in paths if analysis_path(t).exists()]
    if args.only:
        analyses = [a for a in analyses if a["video_id"] == args.only]
    if not analyses:
        sys.exit("No analyses on disk to synthesize from.")

    seg_cache = {
        a["video_id"]: indexed_segments(
            transcript_path_for(a["video_id"], a["source"], a["upload_date"])
        )
        for a in analyses
    }

    party_inputs = {slug: build_party_input(slug, analyses) for slug in parties}
    party_inputs = {slug: data for slug, data in party_inputs.items() if data}
    print(
        f"synthesizing {len(party_inputs)} parties from {len(analyses)} transcripts..."
    )

    POSITIONS_DIR.mkdir(exist_ok=True)
    for i, (slug, party_input) in enumerate(party_inputs.items(), 1):
        name = parties[slug]["name"]
        print(f"[{i}/{len(party_inputs)}] {slug} ({len(party_input)} transcript(s))")
        try:
            positions = synthesize_party(
                client, args.model, slug, name, party_input, seg_cache
            )
        except Exception as e:
            if args.fail_fast:
                sys.exit(f"failed {slug}: {e}")
            warn(f"failed {slug}: {e}")
            continue
        if not positions:
            warn(f"{slug}: no positions produced")
            continue
        out_path = POSITIONS_DIR / f"{slug}.json"
        write_json(out_path, {"slug": slug, "name": name, "positions": positions})
        print(
            f"    wrote {out_path.relative_to(DATA_DIR)} ({len(positions)} positions)"
        )
    print_totals(run_start)


if __name__ == "__main__":
    main()
