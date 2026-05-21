"""Extract and normalize NEBE 7th General Election candidate lists.

Each PDF is a single 8-column table (header repeated per page):

    Region | Constituency | Full Name | Candidate ID | Gender | Disability |
    Party Name | Education Level

`find_tables` only detects the header rule, so we reconstruct rows from word
positions instead: words are bucketed into the eight columns by their x-offset
(taken from the header) and grouped into visual lines by y-offset. A line that
carries a `CID...` token in the Candidate ID column starts a new record; any
line without one is a wrapped continuation and is appended to the record above.

Region identity comes from the file name (authoritative, matching the
polling-stations dataset) so the two datasets join on region. Constituencies
join by (region, body, constituency name): for HoPR the name is the electoral
district ("የምርጫ ክልል N"); for RC it is the sub-region name.

Output (all under data/json/):
  - candidates/{region}_{body}.json  normalized candidate records, one per PDF
  - regions.json                     per-region candidate + constituency counts
  - constituencies.json              hopr / rc constituencies with stable slugs
  - parties.json                     party -> candidate counts (overall + body)
  - index.json                       dataset totals
"""

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import TypedDict

import pymupdf
from rich.console import Console

DATA_DIR = Path(__file__).parent / "data"
PDF_DIR = DATA_DIR / "pdfs"
JSON_DIR = DATA_DIR / "json"
CANDIDATES_DIR = JSON_DIR / "candidates"

# Polling-stations dataset, joined to candidates by constituency (see below).
PS_CONSTITUENCIES = (
    Path(__file__).parent.parent
    / "polling-stations"
    / "data"
    / "json"
    / "constituencies.json"
)

console = Console()

# Canonical region identity keyed by file-name slug (shared with polling-stations).
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
    "south_ethiopia": {"code": "9", "name": "South Ethiopia", "name_am": "ደቡብ ኢትዮጵያ"},
    "south_west": {
        "code": "11",
        "name": "South West Ethiopia",
        "name_am": "ደቡብ ምዕራብ ኢትዮጵያ",
    },
}

BODY_NAMES = {
    "hopr": "House of People's Representatives",
    "rc": "Regional Council",
}

# English names for every party on the candidate lists (the source PDFs give
# only Amharic). Best-effort translations/transliterations; official English
# names are used where the party has one.
ENGLISH_NAMES: dict[str, str] = {
    "ብልፅግና ፓርቲ": "Prosperity Party",
    "ኢዜማ": "Ethiopian Citizens for Social Justice (EZEMA)",
    "ትብብር ለኢትዮጵያ አንድነት": "Coalition for Ethiopian Unity",
    "ነፃነትና እኩልነት ፓርቲ": "Freedom and Equality Party",
    "ሰላም ለኢትዮጵያ ጥምረት": "Peace for Ethiopia Coalition",
    "ህዳሴ ፓርቲ": "Renaissance Party",
    "የዎላይታ ሕዝቦች ነጻነት ንቅናቄ": "Wolaita Peoples Freedom Movement",
    "ባልደራስ ለእውነተኛ ዲሞክራሲ": "Balderas for True Democracy",
    "የኢትዮጵያ ፌዴራላዊ ዴሞክራሲያዊ አንድነት መድረክ": "Ethiopian Federal Democratic Unity Forum (Medrek)",
    "የወሎ ህዝቦች ዲሞክራሲያዊ ፓርቲ": "Wollo Peoples Democratic Party",
    "አዲስ ትውልድ ፓርቲ": "New Generation Party",
    "አርጎባ አንድነት ጀበርቲ": "Argoba Unity Jeberti",
    "የኦጋዴን ብሔራዊ ነፃነት ግንባር": "Ogaden National Liberation Front",
    "የኢትዮጵያ ብሔራዊ አንድነት ፓርቲ": "Ethiopian National Unity Party",
    "የሲዳማ ሕዝብ አንድነት ዴሞክራሲያዊ ድርጅት": "Sidama Peoples Unity Democratic Organization",
    "የአማራ ዲሞክራሲያዊ ሃይል ንቅናቄ": "Amhara Democratic Force Movement",
    "የኢትዮጵያ ዴሞክራቲክ ኅብረት": "Ethiopian Democratic Union",
    "የኦሮሞ ነፃነት ግንባር": "Oromo Liberation Front",
    "ሲዳማ አንድነት ፓርቲ": "Sidama Unity Party",
    "ኅብር ኢትዮጵያ ዲሞክራሲያዊ ፓርቲ": "Hibir Ethiopia Democratic Party",
    "የአፋር ሕዝብ ፓርቲ": "Afar Peoples Party",
    "የዎላይታ ብሔራዊ ንቅናቄ": "Wolaita National Movement",
    "የአፋር ነፃ አውጪ ግንባር ፓርቲ": "Afar Liberation Front Party",
    "ጎጎት ለጉራጌ አንድነት እና ፍትህ ፓርቲ": "Gogot for Gurage Unity and Justice Party",
    "የመላው ሲዳማ ህዝብ ዴሞክራሲያዊ አንድነት ፓርቲ": "All Sidama Peoples Democratic Unity Party",
    "Independent": "Independent",
    "አንድ ኢትዮጵያ ዲሞክራሲ ፓርቲ": "One Ethiopia Democracy Party",
    "የቤኒሻንጉል ህዝብ ነፃነት ንቅናቄ": "Benishangul Peoples Liberation Movement",
    "የአማራ ብሔራዊ ንቅናቄ": "National Movement of Amhara (NaMA)",
    "የዎላይታ ሕዝብ ዴሞክራሲያዊ ግንባር": "Wolaita Peoples Democratic Front",
    "የጉሙዝ ሕዝብ ዴሞክራሲያዊ ንቅናቄ": "Gumuz Peoples Democratic Movement",
    "የቁጫ ሕዝብ ዴሞክራሲያዊ ፓርቲ": "Kucha Peoples Democratic Party",
    "ኅብረት ለዲሞክራሲና ለነፃነት ፓርቲ": "Union for Democracy and Freedom Party",
    "የምዕራብ ሶማሌ ዲሞክራቲክ ፓርቲ": "Western Somali Democratic Party",
    "የቅማንት ዴሞክራሲያዊ ፓርቲ": "Qimant Democratic Party",
    "ጌዴኦ ሕዝብ ዴሞክራሲያዊ ድርጅት": "Gedeo Peoples Democratic Organization",
    "ሱማሌ ፌደራሊስት ፓርቲ": "Somali Federalist Party",
    "ራያ ራዩማ ዴሞክራሲያዊ ፓርቲ": "Raya Rayuma Democratic Party",
    "ዶንጋ ሕዝቦች ዲሞክራሲያዊ ድርጅት": "Donga Peoples Democratic Organization",
    "የኩሽ ህዝቦች ብሔራዊ ንቅናቄ": "Kush Peoples National Movement",
    "የወለኔ ህዝብ ዴሞክራሲያዊ ፓርቲ": "Welene Peoples Democratic Party",
    "አርጎባ ህዝብ ዴሞክራሲያዊ ድርጅት": "Argoba Peoples Democratic Organization",
    "የሐረሪ ዴሞክራሲያዊ ድርጅት": "Harari Democratic Organization",
}

# Bridge to the party-profile dataset (transcripts/data/parties.json), keyed by
# the candidate-list Amharic party name -> the website's English party slug. Only
# parties that have a profile are listed; the rest stay unlinked.
PROFILE_SLUGS: dict[str, str] = {
    "ብልፅግና ፓርቲ": "prosperity-party",
    "ኢዜማ": "ethiopian-citizens-for-social-justice",
    "ትብብር ለኢትዮጵያ አንድነት": "coalition-for-ethiopian-unity-party",
    "ነፃነትና እኩልነት ፓርቲ": "freedom-and-equality-party",
    "ሰላም ለኢትዮጵያ ጥምረት": "peace-for-ethiopia-coalition",
    "ህዳሴ ፓርቲ": "renaissance-party",
    "ባልደራስ ለእውነተኛ ዲሞክራሲ": "balderas-for-true-democracy-party",
    "የኢትዮጵያ ፌዴራላዊ ዴሞክራሲያዊ አንድነት መድረክ": "ethiopian-federal-democratic-unity-forum",
    "የወሎ ህዝቦች ዲሞክራሲያዊ ፓርቲ": "wollo-peoples-democratic-party",
    "አዲስ ትውልድ ፓርቲ": "new-generation-party",
    "የኢትዮጵያ ብሔራዊ አንድነት ፓርቲ": "ethiopian-national-unity-party",
    "የአማራ ዲሞክራሲያዊ ሃይል ንቅናቄ": "amhara-democratic-force-movement",
    "የኢትዮጵያ ዴሞክራቲክ ኅብረት": "ethiopian-democratic-union",
    "የኦሮሞ ነፃነት ግንባር": "oromo-liberation-front",
    "ሲዳማ አንድነት ፓርቲ": "sidama-unity-party",
    "ኅብር ኢትዮጵያ ዲሞክራሲያዊ ፓርቲ": "hibir-ethiopia-democratic-party",
    "የአፋር ሕዝብ ፓርቲ": "afar-peoples-party",
    "ጎጎት ለጉራጌ አንድነት እና ፍትህ ፓርቲ": "gogot-for-gurage-unity-and-justice-party",
    "የአማራ ብሔራዊ ንቅናቄ": "national-movement-of-amhara",
    "የቁጫ ሕዝብ ዴሞክራሲያዊ ፓርቲ": "kucha-peoples-democratic-party",
    "የቅማንት ዴሞክራሲያዊ ፓርቲ": "qimant-democratic-party",
    "ራያ ራዩማ ዴሞክራሲያዊ ፓርቲ": "raya-rayuma-democratic-party",
    "የኩሽ ህዝቦች ብሔራዊ ንቅናቄ": "kush-peoples-national-movement-party",
}

# Column left-edges (pt) read from the header row; a word belongs to the last
# column whose start it clears. Stable across every candidate PDF.
COLUMN_STARTS = [34, 104, 254, 399, 489, 534, 594, 714]
COLUMN_FIELDS = [
    "region",
    "constituency",
    "full_name",
    "candidate_id",
    "gender",
    "disability",
    "party",
    "education",
]

CID_RE = re.compile(r"^CID\d+$")


def column_of(x0: float) -> int:
    col = 0
    for i, start in enumerate(COLUMN_STARTS):
        if x0 >= start - 8:
            col = i
    return col


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def extract_pdf(path: Path) -> list[dict[int, str]]:
    """Reconstruct table rows from word positions; returns column-indexed cells."""
    doc = pymupdf.open(path)
    records: list[dict[int, str]] = []

    for page in doc:
        lines: dict[int, list] = defaultdict(list)
        for word in page.get_text("words"):
            x0, y0 = word[0], word[1]
            lines[round(y0 / 4)].append((x0, word[4]))

        for key in sorted(lines):
            cells: dict[int, str] = {}
            for x0, text in sorted(lines[key]):
                col = column_of(x0)
                cells[col] = (cells.get(col, "") + " " + text).strip()

            if cells.get(0, "") == "Region":  # repeated header
                continue

            cid = cells.get(3, "").replace(" ", "")
            if CID_RE.match(cid):
                records.append(cells)
            elif records:  # wrapped continuation line -> merge into previous
                for col, text in cells.items():
                    records[-1][col] = clean(records[-1].get(col, "") + " " + text)

    doc.close()
    return records


def slugify(value: str) -> str:
    """ASCII slug; falls back to a transliteration-free token for Amharic text."""
    ascii_text = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug


# --- Join with the polling-stations dataset --------------------------------
# Both datasets name constituencies by hand: candidate PDFs bilingually
# ("ጎሬ / Goree") and station PDFs in one language with numeric suffixes that
# split a place into sub-constituencies ("አደኣ 1", "አደኣ 2"). We match them once,
# here, so the website joins purely on the polling-station constituency *code*:
#   1. strip Latin transliteration, compare the bare Amharic names;
#   2. failing that, drop a trailing split-number and compare again, except for
#      the federal "የምርጫ ክልል N" districts, whose number is their identity and
#      which already match exactly.
ETHIOPIC_RE = re.compile(r"[ሀ-፿]")
DISTRICT_PHRASE = "ክልል"  # "የምርጫ ክልል N" (never digit-stripped)


def norm_name(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[A-Za-z]", "", value)).strip()


def strip_trailing_number(value: str) -> str:
    return re.sub(r"\s*\d+$", "", value).strip()


def candidate_segments(name: str) -> list[str]:
    """A candidate name may pack several Amharic names around '/'; yield each."""
    segs = [norm_name(p) for p in name.split("/") if ETHIOPIC_RE.search(p)]
    segs = [s for s in segs if s]
    return segs or [s for s in (norm_name(name),) if s]


def join_polling_stations(constituencies: dict[str, list[dict]]) -> dict:
    """Enrich each candidate constituency with its polling stations, and return
    a polling-station-code -> candidate-constituency lookup for the map."""
    if not PS_CONSTITUENCIES.exists():
        console.print("[yellow]warning[/yellow] polling-stations data not found")
        return {"hopr": {}, "rc": {}}

    ps = json.loads(PS_CONSTITUENCIES.read_text(encoding="utf-8"))
    links: dict[str, dict[str, dict]] = {"hopr": {}, "rc": {}}

    for body in ("hopr", "rc"):
        stations_by_code = {c["code"]: c["stations"] for c in ps[body]}
        primary: dict[str, dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        secondary: dict[str, dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for c in ps[body]:
            name = norm_name(c["name"])
            primary[c["region"]][name].append(c["code"])
            if DISTRICT_PHRASE not in name:
                secondary[c["region"]][strip_trailing_number(name)].append(c["code"])

        for cc in constituencies[body]:
            region = cc["region"]
            codes: list[str] = []
            for seg in candidate_segments(cc["name"]):
                codes += primary[region].get(seg, [])
            if not codes:
                for seg in candidate_segments(cc["name"]):
                    if DISTRICT_PHRASE not in seg:
                        codes += secondary[region].get(strip_trailing_number(seg), [])
            codes = sorted(set(codes), key=lambda c: int(c))
            cc["polling_station_codes"] = codes
            cc["polling_stations"] = sum(stations_by_code.get(c, 0) for c in codes)
            ref = {
                "slug": cc["slug"],
                "name": cc["name"],
                "candidates": cc["candidates"],
            }
            for code in codes:
                links[body].setdefault(code, ref)

    return links


def build_record(region: dict[str, str], body: str, cells: dict[int, str]) -> dict:
    get = lambda i: clean(cells.get(i, ""))  # noqa: E731
    return {
        "region": region["name"],
        "region_native": region["name_am"],
        "region_code": region["code"],
        "body": body,
        "constituency": get(1),
        "candidate_id": get(3).replace(" ", ""),
        "full_name": get(2),
        "gender": get(4),
        "disability": get(5).lower() in {"yes", "true"},
        "party": get(6),
        "education": get(7),
    }


def main() -> None:
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)

    file_summaries: list[dict] = []
    # region_slug -> {body -> {constituency_name -> Counter(party)}}
    constituency_index: dict[str, dict[str, dict[str, Counter]]] = defaultdict(
        lambda: {"hopr": defaultdict(Counter), "rc": defaultdict(Counter)}
    )
    region_totals: dict[str, dict[str, int]] = defaultdict(lambda: {"hopr": 0, "rc": 0})
    party_counts: dict[str, Counter] = defaultdict(Counter)  # party -> body counts
    gender_counts: Counter = Counter()
    education_counts: Counter = Counter()
    disability_count = 0
    total = 0

    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        stem = pdf.stem  # e.g. "oromia_hopr"
        region_slug, _, body = stem.rpartition("_")
        region = REGIONS[region_slug]
        console.print(f"[cyan]extracting[/cyan] {pdf.name} ...")

        records = [build_record(region, body, c) for c in extract_pdf(pdf)]
        (CANDIDATES_DIR / f"{stem}.json").write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        for r in records:
            constituency_index[region_slug][body][r["constituency"]][r["party"]] += 1
            region_totals[region_slug][body] += 1
            party_counts[r["party"]][body] += 1
            gender_counts[r["gender"] or "Unspecified"] += 1
            education_counts[r["education"] or "Not Specified"] += 1
            disability_count += int(r["disability"])
        total += len(records)

        file_summaries.append(
            {
                "file": stem,
                "region": region["name"],
                "body": body,
                "candidates": len(records),
            }
        )
        console.print(f"  [green]{len(records):,}[/green] candidates -> {stem}.json")

    # constituencies.json: stable slug per (region, body, name).
    constituencies: dict[str, list[dict]] = {"hopr": [], "rc": []}
    for region_slug in sorted(constituency_index):
        region = REGIONS[region_slug]
        for body in ("hopr", "rc"):
            names = constituency_index[region_slug][body]
            for i, name in enumerate(sorted(names)):
                parties = names[name]
                constituencies[body].append(
                    {
                        "slug": f"{region_slug}-{body}-{i}",
                        "region_slug": region_slug,
                        "region": region["name"],
                        "region_code": region["code"],
                        "body": body,
                        "name": name,
                        "candidates": sum(parties.values()),
                        "parties": len(parties),
                    }
                )
    station_links = join_polling_stations(constituencies)
    (JSON_DIR / "constituencies.json").write_text(
        json.dumps(constituencies, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Polling-station constituency code -> candidate constituency, per body. The
    # website's map uses this to show "what's on the ballot here" without redoing
    # any name matching.
    (JSON_DIR / "station_links.json").write_text(
        json.dumps(station_links, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    linked = sum(len(v) for v in station_links.values())

    # regions.json
    regions_out = []
    for region_slug in sorted(region_totals):
        region = REGIONS[region_slug]
        idx = constituency_index[region_slug]
        regions_out.append(
            {
                "slug": region_slug,
                "code": region["code"],
                "name": region["name"],
                "name_native": region["name_am"],
                "candidates": region_totals[region_slug]["hopr"]
                + region_totals[region_slug]["rc"],
                "hopr": region_totals[region_slug]["hopr"],
                "rc": region_totals[region_slug]["rc"],
                "hopr_constituencies": len(idx["hopr"]),
                "rc_constituencies": len(idx["rc"]),
            }
        )
    regions_out.sort(key=lambda r: r["name"])
    (JSON_DIR / "regions.json").write_text(
        json.dumps(regions_out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # parties.json: party names are Amharic, so the slug is a stable positional
    # id (parties are ordered by candidate count, then name).
    class PartyOut(TypedDict):
        name: str
        name_en: str
        candidates: int
        hopr: int
        rc: int
        slug: str
        profile_slug: str | None

    parties_out: list[PartyOut] = sorted(
        (
            PartyOut(
                name=name,
                name_en=ENGLISH_NAMES.get(name, name),
                candidates=counts["hopr"] + counts["rc"],
                hopr=counts["hopr"],
                rc=counts["rc"],
                slug="",
                profile_slug=PROFILE_SLUGS.get(name),
            )
            for name, counts in party_counts.items()
        ),
        key=lambda p: (-p["candidates"], p["name"]),
    )
    for i, party in enumerate(parties_out):
        party["slug"] = f"party-{i}"
    (JSON_DIR / "parties.json").write_text(
        json.dumps(parties_out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    total_hopr = sum(rt["hopr"] for rt in region_totals.values())
    index = {
        "total_candidates": total,
        "by_body": {"hopr": total_hopr, "rc": total - total_hopr},
        "hopr_constituency_count": len(constituencies["hopr"]),
        "rc_constituency_count": len(constituencies["rc"]),
        "region_count": len(regions_out),
        "party_count": len(parties_out),
        "with_disability": disability_count,
        "by_gender": dict(gender_counts.most_common()),
        "by_education": dict(education_counts.most_common()),
        "files": file_summaries,
    }
    (JSON_DIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    console.print(
        f"\n[bold green]{total:,} candidates[/bold green] | "
        f"{total_hopr:,} HoPR / {total - total_hopr:,} RC | "
        f"{len(parties_out)} parties | "
        f"{len(constituencies['hopr'])} HoPR + {len(constituencies['rc'])} RC constituencies | "
        f"{linked:,} polling-station constituencies linked"
    )


if __name__ == "__main__":
    main()
