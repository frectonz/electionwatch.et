"""OCR the scanned NEBE result PDFs into structured per-page JSON with Gemini.

Every results PDF is a scan (one full-page image per page; the winners PDFs are
vector outlines with no text layer), so unlike the other pipelines the tables
cannot be read with pymupdf directly. Each page is rendered to PNG and sent to
Gemini with a per-dataset response schema; the parsed rows are cached under
data/ocr/{pdf-stem}/page_NNN.json so re-runs only OCR missing pages.

Usage:
    uv run python ocr.py --api-key KEY
    GEMINI_API_KEY=... uv run python ocr.py
    uv run python ocr.py --only winners_hopr --force
    uv run python ocr.py --workers 8
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pymupdf
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from rich.console import Console

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

DATA_DIR = Path(__file__).parent / "data"
PDF_DIR = DATA_DIR / "pdfs"
OCR_DIR = DATA_DIR / "ocr"

# The scans embed 1530x1980 page images (180 dpi at US letter); rendering at the
# native resolution loses nothing and keeps the upload small.
RENDER_DPI = 180

MAX_ATTEMPTS = 3

# A 429 carrying this means the billing account is empty; retrying cannot help,
# so the run stops immediately rather than burning attempts on every page.
CREDITS_DEPLETED = "prepayment credits are depleted"

console = Console()


class CreditsDepleted(RuntimeError):
    pass


# --- Response schemas, one per dataset --------------------------------------


class WinnerRow(BaseModel):
    region: str = Field(description="Column 1 (ክልል), repeated for merged cells")
    party: str = Field(
        description="Column 3 exactly as printed, incl. any (የግል) suffix"
    )
    seats: int = Field(description="Column 4: seats won by this row")


class RegionTotal(BaseModel):
    region: str
    seats: int = Field(description="Column 2: the region's total council seats")


class WinnersPage(BaseModel):
    rows: list[WinnerRow]
    region_totals: list[RegionTotal]


class ElectedRow(BaseModel):
    region: str
    constituency: str
    candidate: str


class ElectedPage(BaseModel):
    rows: list[ElectedRow]


class VotesRow(BaseModel):
    region: str
    constituency: str
    candidate: str
    votes: int | None = Field(description="Total votes; null only if the cell is blank")


class VotesPage(BaseModel):
    rows: list[VotesRow]


class SummaryPage(BaseModel):
    registered_voters: int
    votes_cast: int
    turnout_pct: float
    abstained_pct: float
    ballots_used: int
    ballots_unused: int
    ballots_invalid: int


TRANSCRIPTION_RULES = """
RULES
  - Transcribe the table on this page EXACTLY as printed, top to bottom. Do not
    skip, merge, reorder, deduplicate, translate or invent rows.
  - Copy Amharic text verbatim, preserving the exact spelling on the page.
  - Some cells are vertically merged: repeat the merged value on every row it
    spans. If a merged cell is blank because its group continues from the
    previous page, use "" and it will be forward-filled later.
  - Bilingual cells like "አለታ ወንዶ / Alatta Wondo" are copied verbatim,
    including the "/" and the Latin part.
  - Numbers are plain integers (no thousands separators).
"""

WINNERS_PROMPT = (
    """This page is from the official results of Ethiopia's 7th General Election,
published by the National Election Board of Ethiopia (NEBE): seats won per
political party (or independent candidate) per region, for the {body}.

The table has 4 columns:
  1. ክልል — region (merged down its group)
  2. የምክር ቤት መቀመጫ ብዛት — the region's total council seats (merged down its group)
  3. የፖለቲካ ፓርቲ / የግል ዕጩ — a party name, or an independent candidate's personal
     name suffixed with (የግል)
  4. ያሸነፉት የወንበር ብዛት — seats won by that party/candidate in that region

Return:
  - rows: one entry per line of column 3, with region (column 1) and seats
    (column 4).
  - region_totals: one entry per region group visible on this page, with
    column 2's value.
"""
    + TRANSCRIPTION_RULES
)

ELECTED_PROMPT = (
    """This page is from the official results of Ethiopia's 7th General Election,
published by the National Election Board of Ethiopia (NEBE): the list of
elected candidates and the constituency they were elected in, for the {body}.

The table has 3 columns:
  1. ክልል — region (merged down its group)
  2. የምርጫ ክልል — constituency (may be merged down a group; may be bilingual)
  3. የዕጩ ስም — the elected candidate's full name

Return rows: one entry per candidate line.
"""
    + TRANSCRIPTION_RULES
)

VOTES_PROMPT = (
    """This page is from the official results of Ethiopia's 7th General Election,
published by the National Election Board of Ethiopia (NEBE): every candidate's
constituency and total votes received, for the {body}.

The table has 4 columns:
  1. ክልል — region
  2. የምርጫ ክልል — constituency (may be bilingual)
  3. የዕጩ ስም — the candidate's full name
  4. ያገኙት ድምጽ — total votes received (integer)

Return rows: one entry per candidate line.
"""
    + TRANSCRIPTION_RULES
)

SUMMARY_PROMPT = """This page is NEBE's one-page national summary of Ethiopia's 7th General
Election (excluding constituencies undergoing recounts or re-elections). It is
a numbered table of seven figures:

  1. የተመዘገቡ መራጮች ቁጥር        -> registered_voters
  2. ድምፅ የሰጡ መራጮች ቁጥር       -> votes_cast
  3. ድምፅ የሰጡ ... መጠን በመቶኛ    -> turnout_pct (as a number, e.g. 95)
  4. ድምፅ ያልሰጡ ... መጠን በመቶኛ   -> abstained_pct
  5. ጥቅም ላይ የዋሉ የድምፅ መስጫ ወረቀቶች   -> ballots_used
  6. ጥቅም ላይ ያልዋሉ የድምፅ መስጫ ወረቀቶች  -> ballots_unused
  7. ከጥቅም ውጭ የሆኑ የድምፅ መስጫ ወረቀቶች  -> ballots_invalid

Read the numbers exactly as printed (drop thousands separators and % signs).
"""

BODY_LABEL = {
    "hopr": "federal House of Peoples' Representatives (HoPR)",
    "rc": "Regional Councils",
}

# pdf stem -> (prompt template, response schema)
DATASETS: dict[str, tuple[str, type[BaseModel]]] = {
    "winners_hopr": (WINNERS_PROMPT, WinnersPage),
    "winners_rc": (WINNERS_PROMPT, WinnersPage),
    "elected_hopr": (ELECTED_PROMPT, ElectedPage),
    "elected_rc": (ELECTED_PROMPT, ElectedPage),
    "votes_hopr": (VOTES_PROMPT, VotesPage),
    "votes_rc": (VOTES_PROMPT, VotesPage),
    "summary_all": (SUMMARY_PROMPT, SummaryPage),
}


def page_path(stem: str, pno: int) -> Path:
    return OCR_DIR / stem / f"page_{pno:03d}.json"


def thinking_for(model: str) -> types.ThinkingConfig:
    """Turn reasoning down as far as the model allows.

    Transcription is not a reasoning task, and left to itself a pro model will
    think for minutes on a single page of a table. The two model families spell
    the setting differently: Gemini 3 takes a `thinking_level`, while 2.5 takes a
    `thinking_budget` in tokens and rejects the former outright.
    """
    if model.startswith("gemini-3"):
        return types.ThinkingConfig(thinking_level="low")
    # 2.5 Pro refuses a budget of 0 (it cannot switch thinking off), and 128 is
    # the smallest it accepts.
    return types.ThinkingConfig(thinking_budget=128)


def page_count(pdf: Path) -> int:
    with pymupdf.open(pdf) as doc:
        return doc.page_count


def render_page(pdf: Path, pno: int) -> bytes:
    with pymupdf.open(pdf) as doc:
        return doc[pno].get_pixmap(dpi=RENDER_DPI).tobytes("png")


def ocr_page(
    client: genai.Client, model: str, pdf: Path, stem: str, pno: int
) -> tuple[int, int]:
    """OCR one page and cache the result; returns (input, output) token counts."""
    prompt_template, schema = DATASETS[stem]
    body = stem.rsplit("_", 1)[1]
    prompt = prompt_template.replace("{body}", BODY_LABEL.get(body, ""))
    png = render_page(pdf, pno)

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=png, mime_type="image/png"),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0,
                    thinking_config=thinking_for(model),
                ),
            )
            parsed = resp.parsed
            if not isinstance(parsed, BaseModel):
                raise RuntimeError(
                    f"no parsed object; raw text: {(resp.text or '')[:300]}"
                )
            # `pages` lets extract.py verify it has every page of this PDF before
            # it forward-fills merged cells across page boundaries.
            out = {"pdf": stem, "page": pno, "pages": page_count(pdf), "model": model}
            out |= parsed.model_dump()
            path = page_path(stem, pno)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            u = resp.usage_metadata
            if u is not None:
                # Thinking tokens bill as output but are reported separately, so
                # counting only `candidates_token_count` understates the spend.
                out_tokens = (u.candidates_token_count or 0) + (
                    u.thoughts_token_count or 0
                )
                return u.prompt_token_count or 0, out_tokens
            return 0, 0
        except Exception as exc:  # noqa: BLE001 - retry any API hiccup
            if CREDITS_DEPLETED in str(exc):
                raise CreditsDepleted from exc
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(5 * attempt)
    raise RuntimeError(f"{stem} page {pno}: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-key", default=os.environ.get("GEMINI_API_KEY"))
    parser.add_argument("--model", default="gemini-3.1-pro-preview")
    parser.add_argument("--only", help="only OCR this pdf stem (e.g. winners_hopr)")
    parser.add_argument("--force", action="store_true", help="re-OCR cached pages")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    if not args.api_key:
        sys.exit("No API key: pass --api-key or set GEMINI_API_KEY (results/.env)")

    client = genai.Client(api_key=args.api_key)

    jobs: list[tuple[Path, str, int]] = []
    for stem in DATASETS:
        if args.only and stem != args.only:
            continue
        pdf = PDF_DIR / f"{stem}.pdf"
        if not pdf.exists():
            console.print(f"[yellow]missing[/yellow] {pdf.name} (run main.py first)")
            continue
        for pno in range(page_count(pdf)):
            if page_path(stem, pno).exists() and not args.force:
                continue
            jobs.append((pdf, stem, pno))

    if not jobs:
        console.print("[green]nothing to do[/green] (all pages cached)")
        return

    console.print(
        f"[cyan]OCR[/cyan] {len(jobs)} page(s) with {args.model}, "
        f"{args.workers} worker(s)"
    )
    tokens_in = tokens_out = done = failed = 0
    depleted = False
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(ocr_page, client, args.model, pdf, stem, pno): (stem, pno)
            for pdf, stem, pno in jobs
        }
        for future in as_completed(futures):
            stem, pno = futures[future]
            try:
                tin, tout = future.result()
                tokens_in += tin
                tokens_out += tout
                done += 1
                console.print(
                    f"[green]ok[/green] {stem} page {pno} "
                    f"({done}/{len(jobs)}, {tin:,} in / {tout:,} out)"
                )
            except CreditsDepleted:
                if not depleted:
                    depleted = True
                    for f in futures:
                        f.cancel()
            except Exception as exc:  # noqa: BLE001
                failed += 1
                console.print(f"[red]error[/red] {exc}")

    console.print(
        f"\n[bold]{done} page(s) OCR'd[/bold], {failed} failed | "
        f"{tokens_in:,} in / {tokens_out:,} out tokens"
    )
    if depleted:
        console.print(
            "\n[bold red]Gemini credits are depleted.[/bold red] Every page OCR'd "
            "so far is cached under data/ocr/ and will be skipped on the next run. "
            "Top up at https://ai.studio/projects, then re-run this command to "
            "resume where it stopped."
        )
    if failed or depleted:
        sys.exit(1)


if __name__ == "__main__":
    main()
