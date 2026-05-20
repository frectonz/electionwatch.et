"""Extract and normalize structured polling-station data from the NEBE PDFs.

Each PDF is a single 20-column table (header repeated per page). The columns are
positionally consistent across all files, with one exception: the `PS_Type` and
`Polling Station ID` columns swap order between files, which we detect from the
header row.

The raw PDFs have several quirks this script normalizes:
  - `status` is one of five Amharic strings that collapse to digital / manual.
  - A few PDFs render narrow columns that clip text, corrupting `region`,
    `region_code`, and `ps_type`. Region identity is recovered from the file name
    (authoritative); `ps_type` is reduced to its trailing digits.
  - `latitude`/`longitude` are blank or `0` when missing; those become null.

Output (all under data/json/):
  - stations/{region}_{type}.json  normalized station records, one array per PDF
  - regions.json                   region code -> names + per-region counts
  - constituencies.json            HoPR / RC constituency code -> name + counts
  - index.json                     dataset totals and per-file counts
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf
from rich.console import Console

DATA_DIR = Path(__file__).parent / "data"
PDF_DIR = DATA_DIR / "pdfs"
JSON_DIR = DATA_DIR / "json"
STATIONS_DIR = JSON_DIR / "stations"

console = Console()

# Canonical region identity keyed by the file-name slug. The numeric codes are
# the official NEBE region codes (recovered from the clean rows of each file).
REGIONS: dict[str, dict[str, str]] = {
    "addis_ababa": {"code": "14", "name": "Addis Ababa", "name_am": "አዲስ አበባ"},
    "afar": {"code": "2", "name": "Afar", "name_am": "አፋር"},
    "amhara": {"code": "3", "name": "Amhara", "name_am": "አማራ"},
    "benshangul_gumz": {
        "code": "6",
        "name": "Benishangul-Gumuz",
        "name_am": "ቤኒሻንጉል ጉሙዝ",
    },
    "central_ethiopia": {
        "code": "7",
        "name": "Central Ethiopia",
        "name_am": "ማዕከላዊ ኢትዮጵያ",
    },
    "diredawa": {"code": "15", "name": "Dire Dawa", "name_am": "ድሬዳዋ"},
    "gambella": {"code": "12", "name": "Gambela", "name_am": "ጋምቤላ"},
    "harari": {"code": "13", "name": "Harari", "name_am": "ሃረሪ"},
    "oromia": {"code": "4", "name": "Oromia", "name_am": "ኦሮሚያ"},
    "sidama": {"code": "8", "name": "Sidama", "name_am": "ሲዳማ"},
    "somali": {"code": "5", "name": "Somali", "name_am": "ሶማሌ"},
    "south_ethiopia": {
        "code": "9",
        "name": "South Ethiopia",
        "name_am": "ደቡብ ኢትዮጵያ",
    },
    "south_west": {
        "code": "11",
        "name": "South West Ethiopia",
        "name_am": "ደቡብ ምዕራብ ኢትዮጵያ",
    },
}

# Canonical field per column position. Indices 13/14 are resolved per-file from
# the header (the PS_Type / Polling Station ID pair swaps order between PDFs).
COLUMNS = [
    "no",
    "_region",  # discarded: clipped in some files, recovered from file name
    "_region_code",  # discarded: see above
    "zone",
    "zone_code",
    "woreda",
    "woreda_code",
    "kebele",
    "kebele_code",
    "hopr_constituency_code",
    "hopr_constituency",
    "rc_constituency_code",
    "rc_constituency",
    None,  # 13: ps_type or polling_station_id
    None,  # 14: the other
    "polling_station_code",
    "name",
    "latitude",
    "longitude",
    "_status",  # discarded: replaced by registration_type
]

# Source `status` strings -> normalized registration type.
DIGITAL_STATUSES = {
    "ሙሉ ለሙሉ የቴክኖሎጂ የመራጮች ምዝገባ",
    "የቴክኖሎጂ የምራጮች ምዝገባ",
    "የቴክኖሎጂ የመራጮች ምዝገባ",
}


def clean(value: str | None) -> str:
    """Collapse internal newlines/whitespace from a wrapped cell."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def registration_type(status: str, file_type: str) -> str:
    """Normalize the Amharic status string to 'digital' or 'manual'."""
    if status in DIGITAL_STATUSES:
        return "digital"
    if status:
        return "manual"
    return file_type  # fall back to the file-name suffix if status is blank


def normalize_ps_type(value: str) -> int | None:
    """`ps_type` is clipped in some files (e.g. 'ዳ1'); keep its trailing digits."""
    m = re.search(r"(\d+)$", value)
    return int(m.group(1)) if m else None


def normalize_coord(lat: str, lon: str) -> tuple[float | None, float | None]:
    """Parse coordinates, treating blanks/zeros/out-of-Ethiopia as missing."""
    try:
        la, lo = float(lat), float(lon)
    except TypeError, ValueError:
        return None, None
    if 3.0 < la < 15.0 and 33.0 < lo < 48.0:
        return la, lo
    return None, None


def resolve_columns(header: list[str]) -> list[str]:
    """Fill in the swappable columns at indices 13/14 from the header row."""
    cols = COLUMNS.copy()
    if "type" in clean(header[13]).lower():
        cols[13], cols[14] = "ps_type", "polling_station_id"
    else:
        cols[13], cols[14] = "polling_station_id", "ps_type"
    return cols


def extract_pdf(path: Path, region: dict[str, str], file_type: str) -> list[dict]:
    """Parse one PDF into normalized station records."""
    doc = pymupdf.open(path)
    records: list[dict] = []
    cols: list[str] | None = None

    for page in doc:
        for table in page.find_tables().tables:
            for row in table.extract():
                first = clean(row[0]) if row else ""
                if not first.isdigit():  # header / stray row
                    if cols is None and len(row) == 20:
                        cols = resolve_columns(row)
                    continue
                if len(row) != 20:
                    continue
                if cols is None:
                    cols = COLUMNS.copy()
                    cols[13], cols[14] = "ps_type", "polling_station_id"

                raw = {name: clean(cell) for name, cell in zip(cols, row)}
                lat, lon = normalize_coord(raw["latitude"], raw["longitude"])
                records.append(
                    {
                        "no": int(raw["no"]),
                        "region": region["name"],
                        "region_native": region["name_am"],
                        "region_code": region["code"],
                        "zone": raw["zone"],
                        "zone_code": raw["zone_code"],
                        "woreda": raw["woreda"],
                        "woreda_code": raw["woreda_code"],
                        "kebele": raw["kebele"],
                        "kebele_code": raw["kebele_code"],
                        "hopr_constituency_code": raw["hopr_constituency_code"],
                        "hopr_constituency": raw["hopr_constituency"],
                        "rc_constituency_code": raw["rc_constituency_code"],
                        "rc_constituency": raw["rc_constituency"],
                        "polling_station_code": raw["polling_station_code"],
                        "polling_station_id": raw["polling_station_id"],
                        "ps_type": normalize_ps_type(raw["ps_type"]),
                        "name": raw["name"],
                        "latitude": lat,
                        "longitude": lon,
                        # "nebe" when the PDF published a coordinate, else null.
                        # NEBE left coordinates blank for ~41% of stations.
                        "coordinate_source": "nebe" if lat is not None else None,
                        "registration_type": registration_type(
                            raw["_status"], file_type
                        ),
                    }
                )

    doc.close()
    return records


def best_name(counter: Counter) -> str:
    """Pick the most common name for a code; break ties by longest (least clipped)."""
    return max(counter.items(), key=lambda kv: (kv[1], len(kv[0])))[0]


def main() -> None:
    STATIONS_DIR.mkdir(parents=True, exist_ok=True)

    file_summaries: list[dict] = []
    region_stats: dict[str, dict] = {}
    hopr_names: dict[str, Counter] = defaultdict(Counter)
    hopr_region: dict[str, str] = {}
    hopr_count: Counter = Counter()
    rc_names: dict[str, Counter] = defaultdict(Counter)
    rc_region: dict[str, str] = {}
    rc_count: Counter = Counter()
    coord_sources: Counter = Counter()

    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        stem = pdf.stem  # e.g. "oromia_manual"
        region_slug, _, file_type = stem.rpartition("_")
        region = REGIONS[region_slug]
        console.print(f"[cyan]extracting[/cyan] {pdf.name} ...")
        records = extract_pdf(pdf, region, file_type)

        (STATIONS_DIR / f"{stem}.json").write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        with_coords = sum(1 for r in records if r["latitude"] is not None)
        digital = sum(1 for r in records if r["registration_type"] == "digital")
        file_summaries.append(
            {
                "file": stem,
                "region": region["name"],
                "registration_type": file_type,
                "stations": len(records),
                "with_coordinates": with_coords,
            }
        )

        rs = region_stats.setdefault(
            region_slug,
            {
                "slug": region_slug,
                "code": region["code"],
                "name": region["name"],
                "name_native": region["name_am"],
                "stations": 0,
                "digital": 0,
                "manual": 0,
                "with_coordinates": 0,
            },
        )
        rs["stations"] += len(records)
        rs["digital"] += digital
        rs["manual"] += len(records) - digital
        rs["with_coordinates"] += with_coords

        for r in records:
            coord_sources[r["coordinate_source"] or "none"] += 1
            if r["hopr_constituency_code"].isdigit():
                code = r["hopr_constituency_code"]
                hopr_names[code][r["hopr_constituency"]] += 1
                hopr_region[code] = r["region"]
                hopr_count[code] += 1
            if r["rc_constituency_code"].isdigit():
                code = r["rc_constituency_code"]
                rc_names[code][r["rc_constituency"]] += 1
                rc_region[code] = r["region"]
                rc_count[code] += 1

        console.print(f"  [green]{len(records):,}[/green] stations -> {stem}.json")

    # regions.json
    regions_out = sorted(region_stats.values(), key=lambda r: r["name"])
    (JSON_DIR / "regions.json").write_text(
        json.dumps(regions_out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # constituencies.json
    def constituency_list(names, region, count) -> list[dict]:
        return sorted(
            (
                {
                    "code": code,
                    "name": best_name(names[code]),
                    "region": region[code],
                    "stations": count[code],
                }
                for code in names
            ),
            key=lambda c: int(c["code"]),
        )

    constituencies = {
        "hopr": constituency_list(hopr_names, hopr_region, hopr_count),
        "rc": constituency_list(rc_names, rc_region, rc_count),
    }
    (JSON_DIR / "constituencies.json").write_text(
        json.dumps(constituencies, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # index.json
    total = sum(s["stations"] for s in file_summaries)
    total_coords = sum(s["with_coordinates"] for s in file_summaries)
    total_digital = sum(r["digital"] for r in regions_out)
    index = {
        "total_stations": total,
        "by_registration_type": {
            "digital": total_digital,
            "manual": total - total_digital,
        },
        "with_coordinates": total_coords,
        "without_coordinates": total - total_coords,
        "coordinate_sources": dict(sorted(coord_sources.items())),
        "region_count": len(regions_out),
        "hopr_constituency_count": len(constituencies["hopr"]),
        "rc_constituency_count": len(constituencies["rc"]),
        "files": file_summaries,
    }
    (JSON_DIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    console.print(
        f"\n[bold green]{total:,} polling stations[/bold green] | "
        f"{total_digital:,} digital / {total - total_digital:,} manual | "
        f"{total_coords:,} with coordinates | "
        f"{len(constituencies['hopr'])} HoPR + {len(constituencies['rc'])} RC constituencies"
    )


if __name__ == "__main__":
    main()
