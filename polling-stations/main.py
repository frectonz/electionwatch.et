"""Download NEBE 7th General Election polling station PDFs.

Source: https://nebe.org.et/en/List_of_polling_stations
"""

from pathlib import Path

import httpx
from rich.console import Console

BASE_URL = "https://nebe.org.et"
DATA_DIR = Path(__file__).parent / "data"
PDF_DIR = DATA_DIR / "pdfs"

console = Console()

# (region, registration_type, source_path)
POLLING_STATION_PDFS = [
    # Digital voter registration
    ("addis_ababa", "digital", "/sites/default/files/addis_ababa_techno.pdf"),
    ("amhara", "digital", "/sites/default/files/amhara_techno.pdf"),
    ("diredawa", "digital", "/sites/default/files/diredawa_techno.pdf"),
    ("oromia", "digital", "/sites/default/files/oromia_techno.pdf"),
    ("sidama", "digital", "/sites/default/files/sidama_techno.pdf"),
    ("somali", "digital", "/sites/default/files/somali_techno.pdf"),
    ("south_ethiopia", "digital", "/sites/default/files/south_ethiopia_techno.pdf"),
    ("central_ethiopia", "digital", "/sites/default/files/central_techno.pdf"),
    # Manual voter registration
    ("afar", "manual", "/sites/default/files/Afar_manuwal.pdf"),
    ("amhara", "manual", "/sites/default/files/amhara_manuwal.pdf"),
    ("benshangul_gumz", "manual", "/sites/default/files/benshangul_manuwal.pdf"),
    ("diredawa", "manual", "/sites/default/files/diredawa_manual.pdf"),
    ("gambella", "manual", "/sites/default/files/gambela_manuwal.pdf"),
    ("harari", "manual", "/sites/default/files/Harari_Manual.pdf"),
    ("oromia", "manual", "/sites/default/files/oromia_manuwal.pdf"),
    ("sidama", "manual", "/sites/default/files/sidama_manuwal.pdf"),
    ("somali", "manual", "/sites/default/files/somali_manuwal.pdf"),
    ("south_ethiopia", "manual", "/sites/default/files/south_ethiopia_manual.pdf"),
    ("central_ethiopia", "manual", "/sites/default/files/central_manuwal.pdf"),
    ("south_west", "manual", "/sites/default/files/south_west_ethiopia_manual.pdf"),
]


def download_pdf(client: httpx.Client, region: str, reg_type: str, path: str) -> None:
    dest = PDF_DIR / f"{region}_{reg_type}.pdf"
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
        for region, reg_type, path in POLLING_STATION_PDFS:
            try:
                download_pdf(client, region, reg_type, path)
            except httpx.HTTPError as exc:
                console.print(f"[red]error[/red] {region}_{reg_type}: {exc}")


if __name__ == "__main__":
    main()
