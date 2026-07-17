"""Derive approximate coordinates for Amhara stations NEBE published without GPS.

NEBE's Amhara PDFs leave every latitude/longitude column blank, but each
station carries its zone and woreda names. Those stations are placed at their
woreda's centroid from OCHA's Ethiopia admin-boundary gazetteer
(data/gazetteer/, downloaded by main.py). The result is an approximate,
woreda-level position, never a station GPS fix; extract.py records it with
`coordinate_source: "woreda_centroid"` so it is never mistaken for one.

Matching works on Amharic-to-Latin transliteration of the printed names
against the gazetteer's English names, compared in similarity tiers (exact,
consonant skeleton, clipped-column prefix, bounded edit distance). Direction
words (East/West/North/South) and the ከተማ (town) / ዙሪያ (surrounding) suffixes
are normalized on both sides. A name may match outside its printed zone only
at high-confidence tiers, because NEBE and the gazetteer disagree on several
zone assignments. Pairs the matcher cannot resolve are pinned in OVERRIDES.
"""

import csv
import re
from pathlib import Path

GAZETTEER_PATH = Path(__file__).parent / "data" / "gazetteer" / "eth_admin3_gzt.csv"

# NEBE zone strings (including clipped-column variants) -> gazetteer zone.
ZONE_MAP = {
    "ሰሜን ጎንደር": "North Gondar",
    "ማዕከላዊ ጎንደር": "Central Gondar",
    "ማዕከላዊ ጎንደ": "Central Gondar",
    "ምዕራብ ጎንደር": "West Gondar",
    "ምዕራብ ጎንደ": "West Gondar",
    "ደቡብ ጎንደር": "South Gondar",
    "ሰሜን ወሎ": "North Wello",
    "ደቡብ ወሎ": "South Wello",
    "ሰሜን ሸዋ": "North Shewa (AM)",
    "ምስራቅ ጎጃም": "East Gojam",
    "ምዕራብ ጎጃም": "West Gojam",
    "ሰሜን ጎጃም": "North Gojam",
    "አዊ": "Awi",
    "ዋግኽምራ ብ": "Wag Hamra",
    "ኦሮሚያ ልዩ ዞ": "Oromo Nationality Administration",
    "ባሕር ዳር ልዩ": "Bahir Dar town Admin",
    "ባሕር ዳር ልዩ ዞን": "Bahir Dar town Admin",
}

# Hand-adjudicated pairs, keyed by the exact printed (zone, woreda) strings.
# Targets are gazetteer (zone, woreda) rows; multiple targets average.
OVERRIDES = {
    ("ማዕከላዊ ጎንደ", "ጭልጋ"): {
        "woredas": [("Central Gondar", "Chilga 1"), ("Central Gondar", "Chilga 2")],
        "note": "NEBE keeps Chilga as one woreda; the gazetteer splits it in "
        "two, so the two centroids are averaged.",
    },
    ("ማዕከላዊ ጎንደ", "ጭልጋ ከተማ"): {
        "woredas": [("Central Gondar", "Aykel town")],
        "note": "Chilga's administrative town appears in the gazetteer under "
        "its own name, Aykel.",
    },
    ("ሰሜን ጎንደር", "ጸገዴ"): {
        "woredas": [("Central Gondar", "Tegede")],
        "note": "The gazetteer's only Tsegede is spelled 'Tegede' and filed "
        "under Central Gondar; the spelling gap is too wide for a cross-zone "
        "fuzzy match to accept.",
    },
    ("ደቡብ ወሎ", "ሐይቅ ከተማ"): {
        "woredas": [("South Wello", "Hike town")],
        "note": "The gazetteer spells Hayk 'Hike'; the vowel order differs "
        "beyond what the consonant-skeleton comparison bridges.",
    },
    ("ምስራቅ ጎጃም", "ጉንጅ ቆለላ"): {
        "woredas": [("North Gojam", "Gonje")],
        "note": "Gonj Kolela is Gonje woreda's full name, printed under East "
        "Gojam while the gazetteer files Gonje under North Gojam.",
    },
}

# Ethiopic consonant per 8-character series starting at U+1200.
SERIES = {
    0x1200: "h", 0x1208: "l", 0x1210: "h", 0x1218: "m", 0x1220: "s",
    0x1228: "r", 0x1230: "s", 0x1238: "sh", 0x1240: "k", 0x1248: "kw",
    0x1250: "k", 0x1260: "b", 0x1268: "v", 0x1270: "t", 0x1278: "ch",
    0x1280: "h", 0x1288: "hw", 0x1290: "n", 0x1298: "ny", 0x12A0: "",
    0x12A8: "k", 0x12B0: "kw", 0x12B8: "h", 0x12C0: "kw", 0x12C8: "w",
    0x12D0: "", 0x12D8: "z", 0x12E0: "zh", 0x12E8: "y", 0x12F0: "d",
    0x12F8: "d", 0x1300: "j", 0x1308: "g", 0x1310: "gw", 0x1318: "g",
    0x1320: "t", 0x1328: "ch", 0x1330: "p", 0x1338: "ts", 0x1340: "ts",
    0x1348: "f", 0x1350: "p",
}  # fmt: skip
VOWELS = ["e", "u", "i", "a", "e", "", "o", "wa"]

# Direction and suffix words -> canonical uppercase markers. The markers
# survive the consonant skeleton, and contradicting markers block a match.
AM_MARKERS = {
    "ምስራቅ": "E",
    "ምዕራብ": "W",
    "ሰሜን": "N",
    "ደቡብ": "S",
    "ዙሪያ": "Z",
    "ዙሪ": "Z",
}
EN_MARKERS = {
    "east": "E",
    "misrak": "E",
    "misraq": "E",
    "west": "W",
    "mirab": "W",
    "north": "N",
    "semen": "N",
    "south": "S",
    "debub": "S",
    "zuria": "Z",
    "zuriya": "Z",
}

TOWN_RE = re.compile(r"\s*ከተማ(\s*አስተዳደር|\s*አስ?|\s*አ)?\s*$|\s*ከተ?\s*$")
ZURIA_RE = re.compile(r"\s*ዙሪያ\s*$")
LIYU_RE = re.compile(r"\s*ልዩ\s*$")


def translit(text: str) -> str:
    out = []
    for word in text.split():
        if word in AM_MARKERS:
            out.append(AM_MARKERS[word])
            continue
        buf = []
        for ch in word:
            cp = ord(ch)
            if 0x1200 <= cp <= 0x137F:
                base = cp - (cp - 0x1200) % 8
                cons = SERIES.get(base)
                if cons is None:
                    continue
                buf.append(cons + VOWELS[(cp - 0x1200) % 8])
            elif ch.isascii() and ch.isalpha():
                buf.append(ch.lower())
        if buf:
            out.append("".join(buf))
    return " ".join(out)


def norm_en(name: str) -> tuple[str, bool]:
    name = re.sub(r"\(.*?\)", " ", name)
    is_town = bool(re.search(r"\btown\b", name, re.I))
    name = re.sub(r"\b(town|city|administration)\b", " ", name, flags=re.I)
    words = []
    for w in re.findall(r"[A-Za-z]+", name):
        lw = w.lower().replace("qu", "kw").replace("q", "k")
        words.append(EN_MARKERS.get(lw, lw))
    return " ".join(words), is_town


def skeleton(s: str) -> str:
    return re.sub(r"[aeiou ]", "", s)


def edit_distance(a: str, b: str, cap: int) -> int:
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def nebe_variants(woreda: str) -> tuple[list[tuple[str, int]], bool]:
    """(transliterated variant, penalty) pairs; penalty 1 marks derived forms."""
    base = re.sub(r"\s+", " ", woreda).strip()
    is_town = bool(TOWN_RE.search(base))
    stripped = TOWN_RE.sub("", base).strip() or base
    forms = [(stripped, 0), (base, 1)]
    for rx in (ZURIA_RE, LIYU_RE):
        alt = rx.sub("", stripped).strip()
        if alt and alt != stripped:
            forms.append((alt, 1))
    no_dir = " ".join(w for w in stripped.split() if w not in AM_MARKERS)
    if no_dir and no_dir != stripped:
        forms.append((no_dir, 1))
    parts = [p.strip() for p in stripped.split("/") if p.strip()]
    if len(parts) > 1:
        forms += [(p, 1) for p in parts]
    out, seen = [], set()
    for f, pen in forms:
        t = translit(f)
        if t and t not in seen:
            seen.add(t)
            out.append((t, pen))
    return out, is_town


def gzt_variants(name: str) -> tuple[list[str], bool]:
    parts = [p.strip() for p in name.split("/") if p.strip()]
    normed, is_town = norm_en(name)
    forms = [normed]
    if len(parts) > 1:
        forms += [norm_en(p)[0] for p in parts]
    return [f for f in forms if f], is_town


def pair_tier(nebe: str, gz: str) -> int | None:
    """0 exact, 1 same skeleton, 2 gz extends nebe (clipped print), 3 edit 1,
    4 edit 2 / nebe extends gz, 5 edit 2 on full names."""
    nd = {c for c in nebe if c.isupper()}
    gd = {c for c in gz if c.isupper()}
    if nd and gd and nd != gd:
        return None
    nf, gf = nebe.replace(" ", ""), gz.replace(" ", "")
    if nf == gf:
        return 0
    ns, gs = skeleton(nebe), skeleton(gz)
    if not ns or not gs:
        return None
    if ns == gs:
        return 1
    if len(ns) >= 3 and len(gs) >= 3:
        if gs.startswith(ns):
            return 2
        if edit_distance(ns, gs, 1) <= 1:
            return 3
        if ns.startswith(gs):
            return 4
    if len(ns) >= 4 and len(gs) >= 4 and edit_distance(ns, gs, 2) <= 2:
        return 4
    if len(nf) >= 4 and len(gf) >= 4 and edit_distance(nf, gf, 2) <= 2:
        return 5
    return None


class Geocoder:
    """Resolves printed Amhara (zone, woreda) pairs to woreda centroids."""

    def __init__(self, gazetteer: Path = GAZETTEER_PATH):
        if not gazetteer.exists():
            raise SystemExit(
                f"gazetteer not found at {gazetteer}; run main.py to download it"
            )
        with gazetteer.open(encoding="utf-8") as fh:
            self.entries = [
                r for r in csv.DictReader(fh) if r["admin1_name"] == "Amhara"
            ]
        for e in self.entries:
            e["_forms"], e["_town"] = gzt_variants(e["admin3name"])
        by_name = {(e["admin2_name"], e["admin3name"]): e for e in self.entries}
        self.overrides: dict[tuple[str, str], tuple[float, float]] = {}
        for key, spec in OVERRIDES.items():
            targets = [by_name[w] for w in spec["woredas"]]
            self.overrides[key] = (
                sum(float(t["lat"]) for t in targets) / len(targets),
                sum(float(t["long"]) for t in targets) / len(targets),
            )
        self.cache: dict[tuple[str, str], tuple[float, float] | None] = {}

    def locate(self, zone: str, woreda: str) -> tuple[float, float] | None:
        key = (zone, woreda)
        if key not in self.cache:
            self.cache[key] = self.overrides.get(key) or self.match(zone, woreda)
        return self.cache[key]

    def match(self, zone: str, woreda: str) -> tuple[float, float] | None:
        gz_zone = ZONE_MAP.get(zone)
        variants, is_town = nebe_variants(woreda)
        scored = []
        for e in self.entries:
            tiers = [
                (t, pen)
                for nf, pen in variants
                for gf in e["_forms"]
                if (t := pair_tier(nf, gf)) is not None
            ]
            if not tiers:
                continue
            tier, pen = min(tiers)
            zone_mismatch = 0 if e["admin2_name"] == gz_zone else 1
            if zone_mismatch and tier > 2:
                continue
            town_mismatch = 0 if is_town == e["_town"] else 1
            scored.append(((town_mismatch, tier, pen, zone_mismatch), e))
        if not scored:
            return None
        best = min(s for s, _ in scored)
        hits = [e for s, e in scored if s == best]
        if len(hits) != 1:
            return None
        return float(hits[0]["lat"]), float(hits[0]["long"])
