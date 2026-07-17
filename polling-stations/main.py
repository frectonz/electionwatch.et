"""Download the polling-station source data.

- NEBE 7th General Election polling station PDFs
  (https://nebe.org.et/en/List_of_polling_stations)
- OCHA's Ethiopia administrative-boundary gazetteer, used to derive
  approximate woreda-centroid coordinates for stations NEBE published
  without GPS (https://data.humdata.org/dataset/cod-ab-eth)
"""

import io
import zipfile
from pathlib import Path

import httpx
from rich.console import Console

BASE_URL = "https://nebe.org.et"
DATA_DIR = Path(__file__).parent / "data"
PDF_DIR = DATA_DIR / "pdfs"
GAZETTEER_DIR = DATA_DIR / "gazetteer"
GAZETTEER_FILES = ["eth_admin3_gzt.csv"]
GAZETTEER_URL = (
    "https://data.humdata.org/dataset/cb58fa1f-687d-4cac-81a7-655ab1efb2d0/"
    "resource/0518da1b-42d1-4624-ad64-768cb69f9d40/download/"
    "eth_admin_boundaries.geojson.zip"
)

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


def download_gazetteer(client: httpx.Client) -> None:
    missing = [f for f in GAZETTEER_FILES if not (GAZETTEER_DIR / f).exists()]
    if not missing:
        console.print("[dim]skip[/dim] gazetteer (already downloaded)")
        return

    console.print(f"[cyan]GET[/cyan] {GAZETTEER_URL}")
    resp = client.get(GAZETTEER_URL, follow_redirects=True)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for name in missing:
            dest = GAZETTEER_DIR / name
            dest.write_bytes(zf.read(name))
            console.print(
                f"[green]wrote[/green] {dest.name} ({dest.stat().st_size:,} bytes)"
            )


def main() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    GAZETTEER_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120) as client:
        for region, reg_type, path in POLLING_STATION_PDFS:
            try:
                download_pdf(client, region, reg_type, path)
            except httpx.HTTPError as exc:
                console.print(f"[red]error[/red] {region}_{reg_type}: {exc}")
        try:
            download_gazetteer(client)
        except httpx.HTTPError as exc:
            console.print(f"[red]error[/red] gazetteer: {exc}")


if __name__ == "__main__":
    main()
