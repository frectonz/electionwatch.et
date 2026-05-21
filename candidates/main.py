"""Download NEBE 7th General Election candidate-list PDFs.

Source: https://nebe.org.et/en/candidate-list

Two legislative bodies per region:
  - hopr: House of People's Representatives (federal)
  - rc:   Regional Council (regional)
"""

from pathlib import Path

import httpx
from rich.console import Console

BASE_URL = "https://nebe.org.et"
DATA_DIR = Path(__file__).parent / "data"
PDF_DIR = DATA_DIR / "pdfs"

console = Console()

# (region_slug, body, source_path). Region slugs match polling-stations so the
# two datasets join cleanly on region.
CANDIDATE_PDFS = [
    # House of People's Representatives
    ("addis_ababa", "hopr", "/sites/default/files/HoPR_AA_Final_EN.pdf"),
    ("afar", "hopr", "/sites/default/files/HoPR_Afara_Final_EN.pdf"),
    ("amhara", "hopr", "/sites/default/files/HoPR_Amhara_Final_EN.pdf"),
    ("benshangul_gumz", "hopr", "/sites/default/files/HoPR_BG_Final_EN.pdf"),
    ("diredawa", "hopr", "/sites/default/files/HoPR_Dire_Final_EN.pdf"),
    ("gambella", "hopr", "/sites/default/files/HoPR_Gambella_Final_EN.pdf"),
    ("harari", "hopr", "/sites/default/files/HoPR_Harari_Final_EN.pdf"),
    ("oromia", "hopr", "/sites/default/files/HoPR_Oro_Final_EN.pdf"),
    ("sidama", "hopr", "/sites/default/files/HoPR_Sidama_Final_EN.pdf"),
    ("somali", "hopr", "/sites/default/files/HoPR_Somali_Final_EN.pdf"),
    ("central_ethiopia", "hopr", "/sites/default/files/HoPR_CE_Final_EN.pdf"),
    ("south_ethiopia", "hopr", "/sites/default/files/HoPR_SE_Final_EN.pdf"),
    ("south_west", "hopr", "/sites/default/files/HoPR_SWE_Final_EN.pdf"),
    # Regional Council
    ("addis_ababa", "rc", "/sites/default/files/RC_AA_Final_EN.pdf"),
    ("afar", "rc", "/sites/default/files/RC_Afar_Final_EN.pdf"),
    ("amhara", "rc", "/sites/default/files/RC_Amhara_Final_EN.pdf"),
    ("benshangul_gumz", "rc", "/sites/default/files/RC_BG_Final_EN.pdf"),
    ("diredawa", "rc", "/sites/default/files/RC_Dire_Final_EN.pdf"),
    ("gambella", "rc", "/sites/default/files/RC_Gambella_Final_En.pdf"),
    ("harari", "rc", "/sites/default/files/RC_Harari_Final_EN.pdf"),
    ("oromia", "rc", "/sites/default/files/RC_Oro_Final_EN.pdf"),
    ("sidama", "rc", "/sites/default/files/RC_Sidama_Final_EN.pdf"),
    ("somali", "rc", "/sites/default/files/RC_Somali_Final_EN.pdf"),
    ("central_ethiopia", "rc", "/sites/default/files/RC_CE_Final_EN.pdf"),
    ("south_ethiopia", "rc", "/sites/default/files/RC_SE_Final_EN.pdf"),
    ("south_west", "rc", "/sites/default/files/RC_SWE_Final_EN.pdf"),
]


def download_pdf(client: httpx.Client, region: str, body: str, path: str) -> None:
    dest = PDF_DIR / f"{region}_{body}.pdf"
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
        for region, body, path in CANDIDATE_PDFS:
            try:
                download_pdf(client, region, body, path)
            except httpx.HTTPError as exc:
                console.print(f"[red]error[/red] {region}_{body}: {exc}")


if __name__ == "__main__":
    main()
