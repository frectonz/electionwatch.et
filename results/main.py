"""Download NEBE 7th General Election result PDFs.

Source: https://nebe.org.et/am/7th-general-election-result-summary
(published 2026-07-08; Amharic only, no English edition exists)

Three result sets, each split by legislative body like the candidate lists:
  - winners: winning parties / independents with seats won per council
  - elected: elected candidates by name and constituency
  - votes:   every candidate's constituency and total votes received
plus one national summary (registration, turnout, ballot accounting), which
NEBE notes excludes constituencies undergoing recounts or re-elections.
"""

from pathlib import Path

import httpx
from rich.console import Console

BASE_URL = "https://nebe.org.et"
DATA_DIR = Path(__file__).parent / "data"
PDF_DIR = DATA_DIR / "pdfs"

console = Console()

# (dataset, body, source_path). Paths are kept percent-encoded exactly as they
# appear on the results page (the file names are Amharic).
RESULT_PDFS = [
    # "አሸናፊ ፖለቲካ ፓርቲዎች እንዲሁም የግል ተወዳዳሪዎች ስምና ለየምክር ቤቱ ያሸነፉትን መቀመጫ ብዛት"
    # winning parties and independents, with seats won per council
    (
        "winners",
        "hopr",
        "/sites/default/files/%E1%8A%A0%E1%88%BD%E1%8A%93%E1%8D%8A%20%E1%8D%96%E1%88%88%E1%89%B2%E1%8A%AB%20%E1%8D%93%E1%88%AD%E1%89%B2%E1%8B%8E%E1%89%BD%20%E1%8A%A5%E1%8A%95%E1%8B%B2%E1%88%81%E1%88%9D%20%E1%8B%A8%E1%8C%8D%E1%88%8D%20%20%E1%89%B0%E1%8B%88%E1%8B%B3%E1%8B%B3%E1%88%AA%E1%8B%8E%E1%89%BD%20%E1%88%B5%E1%88%9D%E1%8A%93%20%E1%88%88%E1%8B%A8%E1%88%9D%E1%8A%AD%E1%88%AD%20%E1%89%A4%E1%89%B1%20%E1%8B%AB%E1%88%B8%E1%8A%90%E1%8D%89%E1%89%B5%E1%8A%95%20%E1%88%98%E1%89%80%E1%88%98%E1%8C%AB%20%E1%89%A5%E1%8B%9B%E1%89%B5%20(HoPR).pdf",
    ),
    (
        "winners",
        "rc",
        "/sites/default/files/%E1%8A%A0%E1%88%BD%E1%8A%93%E1%8D%8A%20%E1%8D%96%E1%88%88%E1%89%B2%E1%8A%AB%20%E1%8D%93%E1%88%AD%E1%89%B2%E1%8B%8E%E1%89%BD%20%E1%8A%A5%E1%8A%95%E1%8B%B2%E1%88%81%E1%88%9D%20%E1%8B%A8%E1%8C%8D%E1%88%8D%20%20%E1%89%B0%E1%8B%88%E1%8B%B3%E1%8B%B3%E1%88%AA%E1%8B%8E%E1%89%BD%20%E1%88%B5%E1%88%9D%E1%8A%93%20%E1%88%88%E1%8B%A8%E1%88%9D%E1%8A%AD%E1%88%AD%20%E1%89%A4%E1%89%B1%20%E1%8B%AB%E1%88%B8%E1%8A%90%E1%8D%89%E1%89%B5%E1%8A%95%20%E1%88%98%E1%89%80%E1%88%98%E1%8C%AB%20%E1%89%A5%E1%8B%9B%E1%89%B5%20(RC)_0.pdf",
    ),
    # "የተመረጡ እጩዎች ስም ዝርዝር የተመረጡበት የምርጫ ክልል"
    # elected candidates, by name and constituency
    (
        "elected",
        "hopr",
        "/sites/default/files/%E1%8B%A8%E1%89%B0%E1%88%98%E1%88%A8%E1%8C%A1%20%E1%8A%A5%E1%8C%A9%E1%8B%8E%E1%89%BD%20%E1%88%B5%E1%88%9D%20%E1%8B%9D%E1%88%AD%E1%8B%9D%E1%88%AD%20%E1%8B%A8%E1%89%B0%E1%88%98%E1%88%A8%E1%8C%A1%E1%89%A0%E1%89%B5%20%E1%8B%A8%E1%88%9D%E1%88%AD%E1%8C%AB%20%E1%8A%AD%E1%88%8D%E1%88%8D%20(HoPR).pdf",
    ),
    (
        "elected",
        "rc",
        "/sites/default/files/%E1%8B%A8%E1%89%B0%E1%88%98%E1%88%A8%E1%8C%A1%20%E1%8A%A5%E1%8C%A9%E1%8B%8E%E1%89%BD%20%E1%88%B5%E1%88%9D%20%E1%8B%9D%E1%88%AD%E1%8B%9D%E1%88%AD%20%E1%8B%A8%E1%89%B0%E1%88%98%E1%88%A8%E1%8C%A1%E1%89%A0%E1%89%B5%20%E1%8B%A8%E1%88%9D%E1%88%AD%E1%8C%AB%20%E1%8A%AD%E1%88%8D%E1%88%8D%20(RC).pdf",
    ),
    # "እጩዎች የተወዳደሩበት የምርጫ ክልል እና ያገኙት ጠቅላላ የድምፅ"
    # every candidate's constituency and total votes received
    (
        "votes",
        "hopr",
        "/sites/default/files/%E1%8A%A5%E1%8C%A9%E1%8B%8E%E1%89%BD%20%E1%8B%A8%E1%89%B0%E1%8B%88%E1%8B%B3%E1%8B%B0%E1%88%A9%E1%89%A0%E1%89%B5%20%E1%8B%A8%E1%88%9D%E1%88%AD%E1%8C%AB%20%E1%8A%AD%E1%88%8D%E1%88%8D%20%E1%8A%A5%E1%8A%93%20%E1%8B%AB%E1%8C%88%E1%8A%99%E1%89%B5%20%E1%8C%A0%E1%89%85%E1%88%8B%E1%88%8B%20%E1%8B%A8%E1%8B%B5%E1%88%9D%E1%8D%85%20(HoPR).pdf",
    ),
    (
        "votes",
        "rc",
        "/sites/default/files/%E1%8A%A5%E1%8C%A9%E1%8B%8E%E1%89%BD%20%E1%8B%A8%E1%89%B0%E1%8B%88%E1%8B%B3%E1%8B%B0%E1%88%A9%E1%89%A0%E1%89%B5%20%E1%8B%A8%E1%88%9D%E1%88%AD%E1%8C%AB%20%E1%8A%AD%E1%88%8D%E1%88%8D%20%E1%8A%A5%E1%8A%93%20%E1%8B%AB%E1%8C%88%E1%8A%99%E1%89%B5%20%E1%8C%A0%E1%89%85%E1%88%8B%E1%88%8B%20%E1%8B%A8%E1%8B%B5%E1%88%9D%E1%8D%85%20(RC)_compressed.pdf",
    ),
    # "የ7ተኛው ጠቅላላ ምርጫ ማጠቃለያ የድጋሜ ቆጠራን እና ድጋሜ ምርጫን ውጤት መረጃ ሳይጨምር"
    # national summary, excluding recount / re-election constituencies
    (
        "summary",
        "all",
        "/sites/default/files/%E1%8B%A87%E1%89%B0%E1%8A%9B%E1%8B%8D%20%E1%8C%A0%E1%89%85%E1%88%8B%E1%88%8B%20%E1%88%9D%E1%88%AD%E1%8C%AB%20%E1%88%9B%E1%8C%A0%E1%89%83%E1%88%88%E1%8B%AB%20%20%E1%8B%A8%E1%8B%B5%E1%8C%8B%E1%88%9C%20%E1%89%86%E1%8C%A0%E1%88%AB%E1%8A%95%20%E1%8A%A5%E1%8A%93%20%E1%8B%B5%E1%8C%8B%E1%88%9C%20%E1%88%9D%E1%88%AD%E1%8C%AB%E1%8A%95%20%E1%8B%8D%E1%8C%A4%E1%89%B5%20%E1%88%98%E1%88%A8%E1%8C%83%20%E1%88%B3%E1%8B%AD%E1%8C%A8%E1%88%9D%E1%88%AD.pdf",
    ),
]


def download_pdf(client: httpx.Client, dataset: str, body: str, path: str) -> None:
    dest = PDF_DIR / f"{dataset}_{body}.pdf"
    if dest.exists():
        console.print(f"[dim]skip[/dim] {dest.name} (already downloaded)")
        return

    url = BASE_URL + path
    console.print(f"[cyan]GET[/cyan] {url}")
    resp = client.get(url, follow_redirects=True)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    console.print(f"[green]wrote[/green] {dest.name} ({len(resp.content):,} bytes)")


def main() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120) as client:
        for dataset, body, path in RESULT_PDFS:
            try:
                download_pdf(client, dataset, body, path)
            except httpx.HTTPError as exc:
                console.print(f"[red]error[/red] {dataset}_{body}: {exc}")


if __name__ == "__main__":
    main()
