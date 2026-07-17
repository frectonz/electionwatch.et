"""Normalize the OCR'd NEBE result tables and join them to the candidates dataset.

Reads the per-page OCR JSON produced by ocr.py (data/ocr/) and links every row
to the existing datasets so the website can join purely on slugs:

  - regions        -> the shared region slugs (same table as candidates/)
  - parties        -> candidates/data/json/parties.json  (slug, name_en, profile_slug)
  - constituencies -> candidates/data/json/constituencies.json (stable slugs)
  - candidates     -> candidates/data/json/candidates/{region}_{body}.json
                      (candidate_id, which also carries the party affiliation
                      that the results PDFs omit)

Amharic names are spelled inconsistently between NEBE publications (ሀ/ሃ/ኃ,
ሰ/ሠ, ጸ/ፀ, ዲ/ዴ...), so matching runs in tiers: first on a homophone-folded key
that preserves vowel orders, then on a consonant skeleton that drops them, and
for personal names finally on the first two name tokens (publications routinely
disagree on the third). A tier only matches when it is unambiguous in scope.

Output (all under data/json/):
  - summary.json               national registration / turnout / ballot figures
  - seats.json                 seats won per party per region + national totals
  - elected.json               elected candidates, linked to constituency + candidate
  - votes/{region}_{body}.json every candidate's votes, linked the same way
  - index.json                 dataset totals + match rates
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from rich.console import Console

DATA_DIR = Path(__file__).parent / "data"
OCR_DIR = DATA_DIR / "ocr"
JSON_DIR = DATA_DIR / "json"
VOTES_DIR = JSON_DIR / "votes"

CAND_JSON = Path(__file__).parent.parent / "candidates" / "data" / "json"

# Hand-adjudicated matches for rows the tiered matcher cannot resolve: OCR
# garbles too far gone, constituency names misread into another region's
# look-alike, Latin-script names the Ethiopic matcher cannot see, and printed
# names shared by two candidates. Keyed by the exact printed strings, so an
# override can never catch anything but the one row it was written for.
OVERRIDES_PATH = Path(__file__).parent / "overrides.json"

SOURCE_URL = "https://nebe.org.et/am/7th-general-election-result-summary"
PUBLISHED = "2026-07-08"

# The gate the elected list must clear against NEBE's separately-published
# seat sheet: a contradiction means a winner was misidentified, so none are
# tolerated; unmatched winners are published without a party rather than
# guessed, so coverage is held high but not at 1.
CONTRADICTIONS_ALLOWED = 0
COVERAGE_REQUIRED = 0.95

console = Console()

# Canonical region identity keyed by file-name slug (shared with candidates and
# polling-stations).
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

BODIES = ("hopr", "rc")

# Results-PDF party spellings that neither matching tier can bridge to the
# candidate-list spelling; printed name -> candidates/parties.json name.
PARTY_OVERRIDES: dict[str, str] = {}

# "(የግል)" marks an independent candidate's personal name in the winners tables.
INDEPENDENT_RE = re.compile(r"[(（]\s*የግል\s*[)）]\s*$")

ETHIOPIC_LO, ETHIOPIC_HI = 0x1200, 0x1380

# Homophone families folded onto one base (family start -> replacement start),
# preserving the vowel order within the family.
FAMILY_FOLDS = [
    (0x1210, 0x1200),  # ሐ -> ሀ
    (0x1280, 0x1200),  # ኀ -> ሀ
    (0x12B8, 0x1200),  # ኸ -> ሀ
    (0x1220, 0x1230),  # ሠ -> ሰ
    (0x12D0, 0x12A0),  # ዐ -> አ
    (0x1340, 0x1338),  # ፀ -> ጸ
]


def fold_char(ch: str) -> str:
    cp = ord(ch)
    for src, dst in FAMILY_FOLDS:
        if src <= cp < src + 8:
            return chr(dst + (cp - src))
    return ch


def am_fold(value: str) -> str:
    """Tier-1 match key: Ethiopic letters + digits only, homophone families
    folded, vowel orders preserved, Latin transliterations dropped."""
    kept = []
    for ch in value or "":
        cp = ord(ch)
        if ETHIOPIC_LO <= cp < ETHIOPIC_HI:
            kept.append(fold_char(ch))
        elif ch.isdigit() or ch.isspace():
            kept.append(ch)
        else:
            kept.append(" ")
    return " ".join("".join(kept).split())


def am_skeleton(value: str) -> str:
    """Tier-2 match key: like am_fold, but every syllable reduced to its base
    (first) order, so vowel-variant spellings like ጀጎል/ጅጎል collide."""
    out = []
    for ch in am_fold(value):
        cp = ord(ch)
        if ETHIOPIC_LO <= cp < ETHIOPIC_HI:
            out.append(chr(cp - ((cp - ETHIOPIC_LO) % 8)))
        else:
            out.append(ch)
    return "".join(out)


def native_part(value: str) -> str:
    """The Amharic half of a bilingual "አለታ ወንዶ / Alatta Wondo" name.

    Both sources write constituency names that way, and the local OCR renders the
    Latin half as Ethiopic-looking noise ("/ ል|8ቪ3 ህሃዐክ66") that survives folding
    and wrecks the key. Everything after the first "/" is therefore dropped.
    """
    return value.split("/", 1)[0] if "/" in value else value


def _match_keys(value: str, partial: bool) -> list[str]:
    """Match keys from strongest to weakest tier.

    The partial tiers are for personal names, where the two sources disagree on,
    drop, or misread one of the three names. An Ethiopian name is given-father-
    grandfather, and the OCR misreads the middle one as often as any other, which
    defeats a leading pair and a trailing pair alike — so first-and-last is a tier
    of its own.
    """
    fold = am_fold(value)
    keys = [fold, am_skeleton(fold)]
    native = am_fold(native_part(value))
    if native and native != fold:
        keys += [native, am_skeleton(native)]
    if partial:
        tokens = fold.split()
        parts = [" ".join(tokens[:2]), " ".join(tokens[-2:])]
        if len(tokens) >= 3:
            parts.append(f"{tokens[0]} {tokens[-1]}")
        for part in parts:
            keys += [part, am_skeleton(part)]
    return keys


def edit_distance(a: str, b: str, limit: int) -> int:
    """Levenshtein distance, giving up (returning limit + 1) once it exceeds limit."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


class NameMatcher[T]:
    """Tiered Amharic name matcher.

    Tiers run strongest-first and a tier only matches when its answer is
    unambiguous within this matcher's scope. The final tier is a bounded edit
    distance over the consonant skeleton, which absorbs the single-character
    misreads the OCR makes on Amharic script (e.g. it reads the printed
    "ንጋቱ ዋጋር ድሳሳ" as "ጌታቱ ዋጋር ድሳሳ"); it is accepted only when exactly one
    candidate lies within the budget, so a near-tie never silently picks one.
    """

    # Roughly one misread character per 8; constituency-scoped matchers can be
    # far more forgiving because unambiguity in a tiny pool does the safety work.
    FUZZY_DIVISOR = 8
    FUZZY_MAX = 3

    def __init__(
        self,
        partial: bool = False,
        fuzzy: bool = False,
        divisor: int | None = None,
        maximum: int | None = None,
    ) -> None:
        self.partial = partial
        self.fuzzy = fuzzy
        self.divisor = divisor or self.FUZZY_DIVISOR
        self.maximum = maximum or self.FUZZY_MAX
        self.tables: list[dict[str, list[T]]] = [{} for _ in _match_keys("", partial)]
        self.skeletons: list[tuple[str, T]] = []

    def add(self, name: str, value: T) -> None:
        for key, table in zip(_match_keys(name, self.partial), self.tables):
            if not key:
                continue
            bucket = table.setdefault(key, [])
            if not any(v is value for v in bucket):
                bucket.append(value)
        skeleton = am_skeleton(native_part(name))
        if self.fuzzy and skeleton:
            self.skeletons.append((skeleton, value))

    def _fuzzy_match(self, printed: str) -> T | None:
        target = am_skeleton(native_part(printed))
        if not target:
            return None
        budget = min(max(1, len(target) // self.divisor), self.maximum)
        best: list[T] = []
        best_distance = budget + 1
        for skeleton, value in self.skeletons:
            distance = edit_distance(target, skeleton, budget)
            if distance > budget:
                continue
            if distance < best_distance:
                best_distance, best = distance, [value]
            elif distance == best_distance and not any(v is value for v in best):
                best.append(value)
        return best[0] if len(best) == 1 else None

    def match(self, printed: str) -> T | None:
        for key, table in zip(_match_keys(printed, self.partial), self.tables):
            bucket = table.get(key)
            if bucket is not None:
                return bucket[0] if len(bucket) == 1 else None
        return self._fuzzy_match(printed) if self.fuzzy else None


def name_matcher() -> "NameMatcher[dict]":
    """Matcher for personal names across a whole region: thousands of people, so
    the fuzzy tier stays tight or it starts finding two plausible answers."""
    return NameMatcher(partial=True, fuzzy=True)


def close_name_matcher() -> "NameMatcher[dict]":
    """Matcher for the handful of people who stood in one constituency. The pool
    is small enough that a generous edit budget still lands on one person or none,
    which is what recovers names the OCR mangled badly."""
    return NameMatcher(partial=True, fuzzy=True, divisor=4, maximum=6)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def ocr_pages(stem: str) -> list[dict] | None:
    """Every OCR'd page of one PDF, in order, or None if the set is incomplete.

    A page can legitimately open with a blank region/constituency cell when its
    group is merged across the page break, so the reader below forward-fills
    from the previous row. That is only sound over a complete, contiguous run of
    pages: fill across a missing page and rows silently inherit the wrong region.
    So a partial OCR run is refused outright rather than published as data.
    """
    dirpath = OCR_DIR / stem
    if not dirpath.exists():
        return None
    pages = [load_json(p) for p in sorted(dirpath.glob("page_*.json"))]
    if not pages:
        return None

    expected = max(p.get("pages") or 0 for p in pages) or len(pages)
    have = {p["page"] for p in pages}
    missing = sorted(set(range(expected)) - have)
    if missing:
        console.print(
            f"[yellow]skip[/yellow] {stem}: {len(have)}/{expected} pages OCR'd "
            f"(missing {missing[:6]}{'...' if len(missing) > 6 else ''}) — "
            f"run [bold]ocr.py --only {stem}[/bold] to finish it"
        )
        return None

    # A sheet stitched from two OCR engines would carry the weaker one's errors
    # under the stronger one's name, so a mixed sheet is refused.
    engines = {p.get("model", "unknown") for p in pages}
    if len(engines) > 1:
        counts = Counter(p.get("model", "unknown") for p in pages)
        detail = ", ".join(f"{n}x {m}" for m, n in counts.most_common())
        console.print(
            f"[yellow]skip[/yellow] {stem}: transcribed by more than one engine "
            f"({detail}) — re-run [bold]ocr.py --only {stem}[/bold] so the whole "
            f"sheet is read by one"
        )
        return None
    return sorted(pages, key=lambda p: p["page"])


def ocr_rows(stem: str) -> list[dict]:
    """All rows of one PDF in page order, merged-cell blanks forward-filled."""
    rows: list[dict] = []
    last: dict[str, str] = {}
    for page in ocr_pages(stem) or []:
        for row in page["rows"]:
            for field in ("region", "constituency"):
                if field in row:
                    value = " ".join((row[field] or "").split())
                    if value:
                        last[field] = value
                    row[field] = last.get(field, "")
            rows.append(row)
    return rows


def complete(stem: str) -> bool:
    return ocr_pages(stem) is not None


def ocr_ready() -> bool:
    return OCR_DIR.exists() and any(OCR_DIR.glob("*/page_*.json"))


# --- Lookups over the candidates dataset ------------------------------------


class Lookups:
    def __init__(self) -> None:
        self.regions: NameMatcher[str] = NameMatcher(fuzzy=True)
        for slug, info in REGIONS.items():
            self.regions.add(info["name_am"], slug)

        self.parties: list[dict] = load_json(CAND_JSON / "parties.json")
        self.party_by_name = {p["name"]: p for p in self.parties}
        self.party_matcher: NameMatcher[dict] = NameMatcher(fuzzy=True)
        for p in self.parties:
            self.party_matcher.add(p["name"], p)

        # (region_slug, body) -> NameMatcher over constituency names -> record
        self.constituencies: dict[tuple[str, str], NameMatcher[dict]] = defaultdict(
            lambda: NameMatcher(fuzzy=True)
        )
        # The same names searched across every region at once: the sheets' region
        # column is a merged cell and cannot be trusted per-row, so the region is
        # read off the matched constituency instead.
        self.constituencies_anywhere: dict[str, NameMatcher[dict]] = defaultdict(
            lambda: NameMatcher(fuzzy=True)
        )
        # exact candidate-list constituency name -> slug (same source, no fuzz)
        cname_slug: dict[tuple[str, str, str], str] = {}
        self.seats_by_constituency: dict[str, int] = {}
        for body in BODIES:
            for c in load_json(CAND_JSON / "constituencies.json")[body]:
                self.constituencies[(c["region_slug"], body)].add(c["name"], c)
                self.constituencies_anywhere[body].add(c["name"], c)
                cname_slug[(c["region_slug"], body, c["name"])] = c["slug"]
                self.seats_by_constituency[c["slug"]] = c["seats"] or 1

        # candidate full-name matchers, scoped per constituency and per region
        self.by_constituency: dict[tuple, NameMatcher[dict]] = defaultdict(
            close_name_matcher
        )
        self.by_region: dict[tuple[str, str], NameMatcher[dict]] = defaultdict(
            name_matcher
        )
        # independents per (region, body), matched by personal name
        self.independents: dict[tuple[str, str], NameMatcher[dict]] = defaultdict(
            name_matcher
        )
        # (body, candidate_id) -> record, for the hand-adjudicated overrides
        self.by_id: dict[tuple[str, str], dict] = {}
        for path in sorted((CAND_JSON / "candidates").glob("*.json")):
            region_slug, _, body = path.stem.rpartition("_")
            for record in load_json(path):
                cslug = cname_slug.get((region_slug, body, record["constituency"]))
                record["constituency_slug"] = cslug
                record["region_slug"] = region_slug
                self.by_id[(body, record["candidate_id"])] = record
                self.by_region[(region_slug, body)].add(record["full_name"], record)
                if cslug:
                    self.by_constituency[(region_slug, body, cslug)].add(
                        record["full_name"], record
                    )
                if record["party"] == "Independent":
                    self.independents[(region_slug, body)].add(
                        record["full_name"], record
                    )

        # (body, printed constituency, printed candidate, votes|None) -> record.
        # The printed strings are whitespace-normalized but otherwise exact.
        self.overrides: dict[tuple, dict] = {}
        for o in load_json(OVERRIDES_PATH)["candidates"]:
            record = self.by_id.get((o["body"], o["candidate_id"]))
            if record is None:
                raise SystemExit(
                    f"overrides.json: {o['candidate_id']} is not a "
                    f"{o['body']} candidate id"
                )
            key = (
                o["body"],
                " ".join(o["constituency"].split()),
                " ".join(o["candidate"].split()),
                o.get("votes"),
            )
            if key in self.overrides:
                raise SystemExit(f"overrides.json: duplicate key {key}")
            self.overrides[key] = record

    def override(self, body: str, row: dict) -> dict | None:
        """The hand-adjudicated match for this printed row, if one exists."""
        constituency = " ".join(row["constituency"].split())
        candidate = " ".join(row["candidate"].split())
        return self.overrides.get(
            (body, constituency, candidate, row.get("votes"))
        ) or self.overrides.get((body, constituency, candidate, None))

    def party(self, printed: str) -> dict | None:
        name = PARTY_OVERRIDES.get(" ".join(printed.split()))
        if name:
            return self.party_by_name.get(name)
        return self.party_matcher.match(printed)

    def candidate(
        self, region_slug: str, body: str, cslug: str | None, printed: str
    ) -> dict | None:
        if cslug:
            found = self.by_constituency[(region_slug, body, cslug)].match(printed)
            if found is not None:
                return found
        return self.by_region[(region_slug, body)].match(printed)


# --- Per-dataset extraction ---------------------------------------------------


def party_fields(party: dict | None) -> dict:
    return {
        "party_slug": party["slug"] if party else None,
        "party_name_en": party["name_en"] if party else None,
        "profile_slug": party["profile_slug"] if party else None,
    }


def canonical(printed: str, authoritative: str | None) -> dict:
    """A candidate's name for display.

    The results PDFs are scans, and the OCR misreads the occasional Amharic
    character, so a matched row is published under the spelling from the
    candidate lists (parsed from real text-layer PDFs) rather than the OCR's.
    `candidate_printed` keeps the scanned spelling whenever the two disagree, so
    a reader can always trace the row back to the source sheet.
    """
    printed = " ".join(printed.split())
    if authoritative is None:
        return {"candidate": printed, "candidate_printed": printed}
    return {
        "candidate": authoritative,
        "candidate_printed": printed if printed != authoritative else None,
    }


def extract_winners(lk: Lookups, body: str, stats: Counter) -> list[dict]:
    """Seats won per party (or independent) per region, one entry per region."""
    stem = f"winners_{body}"
    rows = ocr_rows(stem)

    council_seats: dict[str, int] = {}
    for page in sorted((OCR_DIR / stem).glob("page_*.json")):
        for total in load_json(page).get("region_totals", []):
            slug = lk.regions.match(total["region"])
            if slug is not None:
                council_seats.setdefault(slug, total["seats"])

    by_region: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        region_slug = lk.regions.match(row["region"])
        if region_slug is None:
            stats[f"{stem}_region_unmatched"] += 1
            console.print(f"[yellow]?region[/yellow] {stem}: {row['region']!r}")
            continue
        printed = " ".join(row["party"].split())
        stats[f"{stem}_rows"] += 1

        if INDEPENDENT_RE.search(printed):
            name = INDEPENDENT_RE.sub("", printed).strip()
            record = lk.independents[(region_slug, body)].match(name)
            if record:
                stats[f"{stem}_matched"] += 1
            else:
                console.print(f"[yellow]?independent[/yellow] {stem}: {name!r}")
            by_region[region_slug].append(
                {
                    "party": "Independent",
                    "independent": True,
                    **canonical(name, record["full_name"] if record else None),
                    "candidate_id": record["candidate_id"] if record else None,
                    "seats": row["seats"],
                    **party_fields(lk.party_by_name.get("Independent")),
                }
            )
        else:
            party = lk.party(printed)
            if party:
                stats[f"{stem}_matched"] += 1
            else:
                console.print(f"[yellow]?party[/yellow] {stem}: {printed!r}")
            by_region[region_slug].append(
                {
                    "party": party["name"] if party else printed,
                    "independent": False,
                    "candidate": None,
                    "candidate_printed": None,
                    "candidate_id": None,
                    "seats": row["seats"],
                    **party_fields(party),
                }
            )

    out = []
    for region_slug in sorted(by_region, key=lambda s: REGIONS[s]["name"]):
        won = by_region[region_slug]
        out.append(
            {
                "region_slug": region_slug,
                "region": REGIONS[region_slug]["name"],
                "region_native": REGIONS[region_slug]["name_am"],
                "council_seats": council_seats.get(region_slug),
                "decided_seats": sum(r["seats"] for r in won),
                "won": won,
            }
        )
    return out


def seat_totals(regions: list[dict]) -> dict:
    """National seat totals per party for one body, independents pooled."""
    per_party: dict[str, dict] = {}
    independents = {"seats": 0, "candidates": 0}
    for region in regions:
        for row in region["won"]:
            if row["independent"]:
                independents["seats"] += row["seats"]
                independents["candidates"] += 1
                continue
            key = row["party_slug"] or f"unmatched:{row['party']}"
            entry = per_party.setdefault(
                key,
                {
                    "party": row["party"],
                    "party_slug": row["party_slug"],
                    "party_name_en": row["party_name_en"],
                    "profile_slug": row["profile_slug"],
                    "seats": 0,
                    "regions": 0,
                },
            )
            entry["seats"] += row["seats"]
            entry["regions"] += 1
    parties = sorted(per_party.values(), key=lambda p: (-p["seats"], p["party"]))
    return {
        "decided_seats": sum(r["decided_seats"] for r in regions),
        "council_seats": sum(r["council_seats"] or 0 for r in regions),
        "parties": parties,
        "independents": independents,
    }


def link_row(
    lk: Lookups, body: str, row: dict, stats: Counter, stem: str
) -> dict | None:
    """Resolve one elected/votes OCR row against the candidates dataset."""
    # Hand-adjudicated rows first; the candidate record settles the name, the
    # party, and which constituency the row really belongs to.
    record = lk.override(body, row)
    if record is not None:
        stats[f"{stem}_rows"] += 1
        stats[f"{stem}_constituency_matched"] += 1
        stats[f"{stem}_candidate_matched"] += 1
        stats[f"{stem}_overridden"] += 1
        party = lk.party_by_name.get(record["party"])
        return {
            "region_slug": record["region_slug"],
            "constituency": record["constituency"],
            "constituency_slug": record["constituency_slug"],
            **canonical(row["candidate"], record["full_name"]),
            "candidate_id": record["candidate_id"],
            "party": record["party"],
            **party_fields(party),
        }

    # The constituency column names its own region; the sheet's merged region
    # column is only a fallback.
    constituency = lk.constituencies_anywhere[body].match(row["constituency"])
    region_slug = (
        constituency["region_slug"] if constituency else lk.regions.match(row["region"])
    )
    if region_slug is None:
        stats[f"{stem}_region_unmatched"] += 1
        console.print(f"[yellow]?region[/yellow] {stem}: {row['region']!r}")
        return None
    stats[f"{stem}_rows"] += 1

    if constituency is None:
        constituency = lk.constituencies[(region_slug, body)].match(row["constituency"])
    cslug = constituency["slug"] if constituency else None
    if cslug:
        stats[f"{stem}_constituency_matched"] += 1

    record = lk.candidate(region_slug, body, cslug, row["candidate"])
    if record:
        stats[f"{stem}_candidate_matched"] += 1
    party = lk.party_by_name.get(record["party"]) if record else None

    # A matched candidate names their own constituency; when the constituency
    # column is misread past recognition, the candidate record supplies it.
    if cslug is None and record and record.get("constituency_slug"):
        cslug = record["constituency_slug"]
        region_slug = record["region_slug"]
        constituency = {"name": record["constituency"], "slug": cslug}
        stats[f"{stem}_constituency_matched"] += 1

    return {
        "region_slug": region_slug,
        "constituency": (
            constituency["name"]
            if constituency
            else " ".join(row["constituency"].split())
        ),
        "constituency_slug": cslug,
        **canonical(row["candidate"], record["full_name"] if record else None),
        "candidate_id": record["candidate_id"] if record else None,
        "party": record["party"] if record else None,
        **party_fields(party),
    }


def extract_elected(lk: Lookups, body: str, stats: Counter) -> list[dict]:
    """NEBE's own list of elected members: who holds each seat.

    This is the authoritative answer and is used as such. It is not inferred from
    the vote counts, because a single row misread on a vote sheet would silently
    hand the seat to the runner-up; `verify_winners` checks this list against the
    seat sheet, a third document, before any of it is published.
    """
    stem = f"elected_{body}"
    out = []
    for row in ocr_rows(stem):
        linked = link_row(lk, body, row, stats, stem)
        if linked:
            out.append(linked)
    return out


def extract_votes(lk: Lookups, body: str, stats: Counter) -> dict[str, list[dict]]:
    """Every candidate's vote count, grouped by region slug."""
    stem = f"votes_{body}"
    by_region: dict[str, list[dict]] = defaultdict(list)
    for row in ocr_rows(stem):
        linked = link_row(lk, body, row, stats, stem)
        if not linked:
            continue
        linked["votes"] = row.get("votes")
        if row.get("votes") is None:
            stats[f"{stem}_votes_missing"] += 1
        by_region[linked.pop("region_slug")].append(linked)
    return by_region


def elected_key(row: dict) -> tuple:
    """Identity of an elected member, for tying the two sheets together."""
    return (
        row.get("constituency_slug") or am_fold(row["constituency"]),
        am_fold(row["candidate"]),
    )


def rank_and_flag(
    body: str, by_region: dict[str, list[dict]], elected: list[dict]
) -> None:
    """Rank each constituency's candidates by votes and flag the elected ones.

    The flag comes from NEBE's elected list, never from the ranking, so a seat is
    only ever awarded by the document that awards it. The rank is what lets the
    site show a race: who came first, and by how much over the rest.
    """
    ids = {e["candidate_id"] for e in elected if e["candidate_id"]}
    keys = {elected_key(e) for e in elected}

    for rows in by_region.values():
        by_constituency: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            row["elected"] = (
                row["candidate_id"] in ids if row["candidate_id"] else False
            ) or elected_key(row) in keys
            row["rank"] = None
            if row["constituency_slug"] and row["votes"] is not None:
                by_constituency[row["constituency_slug"]].append(row)

        for contenders in by_constituency.values():
            contenders.sort(key=lambda r: -(r["votes"] or 0))
            for i, row in enumerate(contenders):
                row["rank"] = i + 1


def verify_winners(elected: list[dict], seats: dict, body: str) -> dict:
    """Check the elected list against NEBE's own seat sheet, a separate document.

    Two failures hide inside a single "agreement" number, and they could not be
    less alike:

      * a **contradiction** — a party is credited with more seats in a region than
        the seat sheet awards it. Something is genuinely wrong: a name was matched
        to the wrong person, or a row to the wrong region. This must be zero.
      * an **unattributed** seat — the winner is named, but the matcher could not
        tie them to a candidate record, so no party can be credited. Nothing is
        wrong; a fact is simply missing, and the site can say so.

    Conflating the two would either hide a real error behind a good-looking score,
    or withhold a sound dataset over a handful of names NEBE itself spells two
    different ways across its own sheets.
    """
    attributed: Counter = Counter()
    unattributed = 0
    for row in elected:
        if not row["party_slug"]:
            unattributed += 1
            continue
        attributed[(row["region_slug"], row["party_slug"])] += 1

    published: Counter = Counter()
    for region in seats[body]["regions"]:
        for won in region["won"]:
            key = (region["region_slug"], won["party_slug"] or won["party"])
            published[key] += won["seats"]

    agree = sum(min(attributed[k], published[k]) for k in published)
    contradictions = sum(
        max(0, attributed[k] - published[k]) for k in set(attributed) | set(published)
    )
    total = sum(published.values())
    return {
        "elected_members": len(elected),
        "published_seats": total,
        "agreeing_seats": agree,
        "unattributed_seats": unattributed,
        "contradicting_seats": contradictions,
        "agreement": round(agree / total, 4) if total else 0,
    }


def rate(stats: Counter, stem: str, field: str) -> str:
    total = stats[f"{stem}_rows"]
    return f"{stats[f'{stem}_{field}']}/{total}" if total else "0/0"


def main() -> None:
    if not ocr_ready():
        console.print(
            "[red]no OCR data[/red] under data/ocr/ — run "
            "[bold]uv run python ocr.py[/bold] first (needs GEMINI_API_KEY)"
        )
        raise SystemExit(1)

    JSON_DIR.mkdir(parents=True, exist_ok=True)
    VOTES_DIR.mkdir(parents=True, exist_ok=True)
    lk = Lookups()
    stats: Counter = Counter()
    files: list[dict] = []

    # Outputs are rewritten from scratch; files this run can't produce are
    # cleared first so a skipped sheet leaves no stale JSON behind.
    for stale in (
        JSON_DIR / "summary.json",
        JSON_DIR / "seats.json",
        JSON_DIR / "elected.json",
        *VOTES_DIR.glob("*.json"),
    ):
        stale.unlink(missing_ok=True)

    # summary.json
    if complete("summary_all"):
        page = load_json(OCR_DIR / "summary_all" / "page_000.json")
        summary = {
            k: page[k]
            for k in (
                "registered_voters",
                "votes_cast",
                "turnout_pct",
                "abstained_pct",
                "ballots_used",
                "ballots_unused",
                "ballots_invalid",
            )
        }
        summary |= {
            "excludes_recounts_and_reruns": True,
            "source_url": SOURCE_URL,
            "published": PUBLISHED,
        }
        write_json(JSON_DIR / "summary.json", summary)
        console.print("[green]wrote[/green] summary.json")

    # seats.json
    seats: dict[str, dict] = {}
    for body in BODIES:
        if not complete(f"winners_{body}"):
            continue
        regions = extract_winners(lk, body, stats)
        seats[body] = {"regions": regions, **seat_totals(regions)}
        console.print(
            f"[cyan]winners_{body}[/cyan] "
            f"{rate(stats, f'winners_{body}', 'matched')} rows matched to parties"
        )
    if seats:
        write_json(JSON_DIR / "seats.json", seats)
        console.print("[green]wrote[/green] seats.json")

    # elected.json + votes/
    elected_out: dict[str, list[dict]] = {}
    verification: dict[str, dict] = {}
    total_votes_rows = 0
    for body in BODIES:
        stem = f"elected_{body}"
        # Winners and vote breakdowns come from different sheets and are gated
        # separately.
        if not complete(stem):
            continue

        winners = extract_elected(lk, body, stats)
        console.print(
            f"[cyan]{stem}[/cyan] {stats[f'{stem}_rows']} rows | "
            f"constituencies {rate(stats, stem, 'constituency_matched')} | "
            f"candidates {rate(stats, stem, 'candidate_matched')}"
        )

        # Reproducing the seat sheet's per-party counts from the elected list is
        # the check that the transcription is sound, not merely plausible.
        if body not in seats:
            continue
        report = verify_winners(winners, seats, body)
        verification[body] = report
        bad = report["contradicting_seats"]
        coverage = report["agreement"]
        published_to_site = (
            bad <= CONTRADICTIONS_ALLOWED and coverage >= COVERAGE_REQUIRED
        )
        verification[body]["published_to_site"] = published_to_site

        if bad > CONTRADICTIONS_ALLOWED:
            console.print(
                f"[red]withheld {body}[/red] {bad} seat(s) are credited to a party "
                f"the seat sheet does not award them — a winner has been "
                f"misidentified, so nothing is published for this body."
            )
            continue
        if coverage < COVERAGE_REQUIRED:
            console.print(
                f"[red]withheld {body}[/red] only {report['agreeing_seats']}/"
                f"{report['published_seats']} ({coverage:.0%}) of seats could be "
                f"attributed, below the {COVERAGE_REQUIRED:.0%} bar."
            )
            continue

        console.print(
            f"[green]verify {body}[/green] no contradictions; "
            f"{report['agreeing_seats']}/{report['published_seats']} "
            f"({coverage:.0%}) of the seats NEBE's seat sheet awards are matched, "
            f"{report['unattributed_seats']} winner(s) named but not tied to a "
            f"candidate record"
        )
        elected_out[body] = winners

        vstem = f"votes_{body}"
        if not complete(vstem):
            continue
        by_region = extract_votes(lk, body, stats)
        rank_and_flag(body, by_region, winners)
        console.print(
            f"[cyan]{vstem}[/cyan] {stats[f'{vstem}_rows']} rows | "
            f"constituencies {rate(stats, vstem, 'constituency_matched')} | "
            f"candidates {rate(stats, vstem, 'candidate_matched')}"
        )
        for region_slug, rows in sorted(by_region.items()):
            path = VOTES_DIR / f"{region_slug}_{body}.json"
            write_json(path, rows)
            files.append(
                {
                    "file": path.stem,
                    "region": REGIONS[region_slug]["name"],
                    "body": body,
                    "rows": len(rows),
                }
            )
            total_votes_rows += len(rows)

    if elected_out:
        write_json(JSON_DIR / "elected.json", elected_out)
        console.print("[green]wrote[/green] elected.json")

    # index.json
    index = {
        "seats": {
            body: {
                "decided_seats": seats[body]["decided_seats"],
                "council_seats": seats[body]["council_seats"],
                "parties": len(seats[body]["parties"]),
                "independent_seats": seats[body]["independents"]["seats"],
            }
            for body in seats
        },
        "elected": {body: len(rows) for body, rows in elected_out.items()},
        "votes_rows": total_votes_rows,
        "verification": verification,
        "match": {
            stem: {
                "rows": stats[f"{stem}_rows"],
                "constituency_matched": stats[f"{stem}_constituency_matched"],
                "candidate_matched": stats[f"{stem}_candidate_matched"],
            }
            for stem in ("elected_hopr", "elected_rc", "votes_hopr", "votes_rc")
            if stats[f"{stem}_rows"]
        },
        "source_url": SOURCE_URL,
        "published": PUBLISHED,
        "files": files,
    }
    write_json(JSON_DIR / "index.json", index)
    console.print("[green]wrote[/green] index.json")


if __name__ == "__main__":
    main()
