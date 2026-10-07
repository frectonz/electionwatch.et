"""Derive approximate coordinates for stations NEBE published without GPS.

Every station carries its region, zone and woreda names. Stations without
coordinates are placed at their woreda's centroid from OCHA's Ethiopia
admin-boundary gazetteer (data/gazetteer/, downloaded by main.py). The result
is an approximate, woreda-level position, never a station GPS fix; extract.py
records it with `coordinate_source: "woreda_centroid"` so it is never mistaken
for one.

Matching works on Amharic-to-Latin transliteration of the printed names
against the gazetteer's English names, compared in similarity tiers (exact,
consonant skeleton, clipped-column prefix, bounded edit distance). Direction
words (East/West/North/South) and the ከተማ (town) / ዙሪያ (surrounding) / ወረዳ
suffixes are normalized on both sides. The printed zone is resolved to a
gazetteer zone first (ZONE_MAP, else the same fuzzy comparison); a woreda in
that zone wins over a namesake elsewhere, and a name may match outside its
zone only at high-confidence tiers. When no woreda matches, a city
administration zone (ሸገር ከተማ አስተዳደር, ሞያሌ ከተማ, an Addis Ababa sub-city) falls
back to the gazetteer's entry for the town itself. Pairs the matcher cannot
resolve are pinned in OVERRIDES.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import TypedDict

GAZETTEER_PATH = Path(__file__).parent / "data" / "gazetteer" / "eth_admin3_gzt.csv"


class Override(TypedDict):
    woredas: list[tuple[str, str]]
    note: str


# (region, NEBE zone string incl. clipped-column variants) -> gazetteer zone.
ZONE_MAP: dict[tuple[str, str], str] = {
    ("Amhara", "ሰሜን ጎንደር"): "North Gondar",
    ("Amhara", "ማዕከላዊ ጎንደር"): "Central Gondar",
    ("Amhara", "ማዕከላዊ ጎንደ"): "Central Gondar",
    ("Amhara", "ምዕራብ ጎንደር"): "West Gondar",
    ("Amhara", "ምዕራብ ጎንደ"): "West Gondar",
    ("Amhara", "ደቡብ ጎንደር"): "South Gondar",
    ("Amhara", "ሰሜን ወሎ"): "North Wello",
    ("Amhara", "ደቡብ ወሎ"): "South Wello",
    ("Amhara", "ሰሜን ሸዋ"): "North Shewa (AM)",
    ("Amhara", "ምስራቅ ጎጃም"): "East Gojam",
    ("Amhara", "ምዕራብ ጎጃም"): "West Gojam",
    ("Amhara", "ሰሜን ጎጃም"): "North Gojam",
    ("Amhara", "አዊ"): "Awi",
    ("Amhara", "ዋግኽምራ ብ"): "Wag Hamra",
    ("Amhara", "ኦሮሚያ ልዩ ዞ"): "Oromo Nationality Administration",
    ("Amhara", "ባሕር ዳር ልዩ"): "Bahir Dar town Admin",
    ("Amhara", "ባሕር ዳር ልዩ ዞን"): "Bahir Dar town Admin",
    ("Oromia", "ደቡብ ምዕራብ"): "South West Shewa",
}

# Hand-adjudicated pairs, keyed by the exact printed (zone, woreda) strings.
# Targets are gazetteer (zone, woreda) rows; multiple targets average.
OVERRIDES: dict[tuple[str, str, str], Override] = {
    ("Amhara", "ማዕከላዊ ጎንደ", "ጭልጋ"): {
        "woredas": [("Central Gondar", "Chilga 1"), ("Central Gondar", "Chilga 2")],
        "note": "NEBE keeps Chilga as one woreda; the gazetteer splits it in "
        "two, so the two centroids are averaged.",
    },
    ("Amhara", "ማዕከላዊ ጎንደ", "ጭልጋ ከተማ"): {
        "woredas": [("Central Gondar", "Aykel town")],
        "note": "Chilga's administrative town appears in the gazetteer under "
        "its own name, Aykel.",
    },
    ("Amhara", "ሰሜን ጎንደር", "ጸገዴ"): {
        "woredas": [("Central Gondar", "Tegede")],
        "note": "The gazetteer's only Tsegede is spelled 'Tegede' and filed "
        "under Central Gondar; the spelling gap is too wide for a cross-zone "
        "fuzzy match to accept.",
    },
    ("Amhara", "ደቡብ ወሎ", "ሐይቅ ከተማ"): {
        "woredas": [("South Wello", "Hike town")],
        "note": "The gazetteer spells Hayk 'Hike'; the vowel order differs "
        "beyond what the consonant-skeleton comparison bridges.",
    },
    ("Amhara", "ምስራቅ ጎጃም", "ጉንጅ ቆለላ"): {
        "woredas": [("North Gojam", "Gonje")],
        "note": "Gonj Kolela is Gonje woreda's full name, printed under East "
        "Gojam while the gazetteer files Gonje under North Gojam.",
    },
    ("Oromia", "ሆሮ ጉዱሩ ወ", "ሀባቦ ጉድሩ"): {
        "woredas": [("Horo Gudru Wellega", "Guduru")],
        "note": "Hababo Guduru is the gazetteer's Guduru woreda.",
    },
    ("Oromia", "ምዕራብ ወለጋ", "ቆንዳላ"): {
        "woredas": [("West Wellega", "Gudetu Kondole")],
        "note": "Kondala is the gazetteer's Gudetu Kondole woreda.",
    },
    ("Oromia", "ምዕራብ ወለጋ", "ባቦ ጋምቤል"): {
        "woredas": [("West Wellega", "Babo")],
        "note": "Babo Gambel is the gazetteer's Babo woreda.",
    },
    ("Oromia", "ባሌ", "ደሎ መና"): {
        "woredas": [("Bale", "Mena (Bale)")],
        "note": "Delo Mena is the gazetteer's Mena woreda in Bale.",
    },
    ("Oromia", "ምስራቅ ባሌ", "ዳዌ ሰረር"): {
        "woredas": [("East Bale", "Dawe Ketchen")],
        "note": "The gazetteer's Dawe Serer row has no coordinates; the "
        "neighbouring Dawe Ketchen stands in.",
    },
    ("Oromia", "ምስራቅ ቦረና", "ወላቡ ሊጣ"): {
        "woredas": [("East Borena", "Meda Welabu"), ("East Borena", "West Welabu")],
        "note": "Welabu Lita is not in the gazetteer; the two Welabu woredas "
        "it was split from are averaged.",
    },
    ("Oromia", "ሰሜን ሸዋ", "አቢቹ ኛኣ"): {
        "woredas": [("North Shewa (OR)", "Abichugna Gne'a")],
        "note": "The gazetteer's spelling of Abichu Gne'a is too far from the "
        "transliteration for the fuzzy tiers.",
    },
    ("Oromia", "ምስራቅ ሸዋ", "መቂ ከተማ"): {
        "woredas": [("East Shewa", "Dugda")],
        "note": "Meki town is not in the gazetteer; it is the seat of Dugda.",
    },
    ("Oromia", "ባሌ", "ወልታኢ ጨፌ"): {
        "woredas": [("Bale", "Sinana")],
        "note": "A kebele printed as its own woreda; its constituency is Sinana.",
    },
    ("Oromia", "ባሌ", "ዳዋ ቃጫን"): {
        "woredas": [("East Bale", "Dawe Ketchen")],
        "note": "Dawa Kachen is Dawe Ketchen, printed under Bale instead of East Bale.",
    },
    ("Afar", "ማሂ ራሱ", "አዳዓዶ"): {
        "woredas": [("Gabi /Zone 3", "Gewane")],
        "note": "Adaado is not in the gazetteer; every station in it belongs to the "
        "Gewane constituency.",
    },
    ("Somali", "ዶሎ", "ቦህ"): {
        "woredas": [("Doolo", "Bokh")],
        "note": "Boh is the gazetteer's Bokh; the name is too short for the "
        "edit-distance tiers.",
    },
    ("Somali", "ሊበን", "ቀርሳ ዱላ"): {
        "woredas": [("Liban", "Filtu"), ("Liban", "Dolo Ado")],
        "note": "The gazetteer's Qarsadula row has no coordinates; the two "
        "woredas it lies between are averaged.",
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
    "ምስራቃዊ": "E",
    "ምዕራብ": "W",
    "ምዕራባዊ": "W",
    "ሰሜን": "N",
    "ሰሜናዊ": "N",
    "ደቡብ": "S",
    "ደቡባዊ": "S",
    "ዙሪያ": "Z",
    "ዙሪ": "Z",
}
EN_MARKERS = {
    "east": "E",
    "eastern": "E",
    "misrak": "E",
    "misraq": "E",
    "west": "W",
    "western": "W",
    "mirab": "W",
    "north": "N",
    "northern": "N",
    "semen": "N",
    "south": "S",
    "southern": "S",
    "debub": "S",
    "zuria": "Z",
    "zuriya": "Z",
}

TOWN_RE = re.compile(r"\s*ከተማ(\s*አስተዳደር|\s*አስ?|\s*አ)?\s*$|\s*ከተ?\s*$")
ZURIA_RE = re.compile(r"\s*ዙሪያ\s*$")
LIYU_RE = re.compile(r"\s*ልዩ\s*$")
WOREDA_RE = re.compile(r"\s+(ወረዳ|ወረ|ወ)\s*$")
SUBZONE_RE = re.compile(r"\s*ክፍለ\s*ከተማ\s*$")


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
    stripped = WOREDA_RE.sub("", stripped).strip() or stripped
    forms = [(stripped, 0), (base, 1)]
    for rx in (ZURIA_RE, LIYU_RE):
        alt = rx.sub("", stripped).strip()
        if alt and alt != stripped:
            forms.append((alt, 1))
    no_dir = " ".join(w for w in stripped.split() if w not in AM_MARKERS and w != "እና")
    if no_dir and no_dir != stripped:
        forms.append((no_dir, 1))
    parts = [p.strip() for p in stripped.split("/") if p.strip()]
    if len(parts) > 1:
        forms += [(p, 1) for p in parts]
    words = stripped.split()
    if len(words) == 2:
        forms.append((f"{words[1]} {words[0]}", 1))
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


def pair_tier(nebe: str, gz: str, short_ok: bool = False) -> int | None:
    """0 exact, 1 same skeleton, 2 gz extends nebe (clipped print), 3 edit 1,
    4 edit 2 / nebe extends gz, 5 edit 2 on full names. Two-consonant
    skeletons only count as tier 1 when `short_ok`."""
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
    if ns == gs and (short_ok or len(ns) >= 3):
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
    """Resolves printed (region, zone, woreda) triples to woreda centroids."""

    def __init__(self, gazetteer: Path = GAZETTEER_PATH):
        if not gazetteer.exists():
            raise SystemExit(
                f"gazetteer not found at {gazetteer}; run main.py to download it"
            )
        with gazetteer.open(encoding="utf-8") as fh:
            entries = [r for r in csv.DictReader(fh) if r["lat"] and r["long"]]
        for e in entries:
            e["_forms"], e["_town"] = gzt_variants(e["admin3name"])
        self.by_region: dict[str, list[dict]] = defaultdict(list)
        for e in entries:
            self.by_region[e["admin1_name"]].append(e)
        by_name = {(e["admin2_name"], e["admin3name"]): e for e in entries}
        self.overrides: dict[tuple[str, str, str], tuple[float, float]] = {}
        for key, spec in OVERRIDES.items():
            targets = [by_name[w] for w in spec["woredas"]]
            self.overrides[key] = (
                sum(float(t["lat"]) for t in targets) / len(targets),
                sum(float(t["long"]) for t in targets) / len(targets),
            )
        self.cache: dict[tuple[str, str, str], tuple[float, float] | None] = {}
        self.zone_cache: dict[tuple[str, str], str | None] = {}

    def locate(self, region: str, zone: str, woreda: str) -> tuple[float, float] | None:
        key = (region, zone, woreda)
        if key not in self.cache:
            self.cache[key] = self.overrides.get(key) or self.match(
                region, zone, woreda
            )
        return self.cache[key]

    def resolve_zone(self, region: str, zone: str) -> str | None:
        key = (region, zone)
        if key in self.zone_cache:
            return self.zone_cache[key]
        gz_zone = ZONE_MAP.get(key)
        if gz_zone is None:
            variants, _ = nebe_variants(zone)
            scored = []
            for gz in {e["admin2_name"] for e in self.by_region[region]}:
                tiers = [
                    (t, pen)
                    for nf, pen in variants
                    for gf in gzt_variants(gz)[0]
                    if (t := pair_tier(nf, gf, short_ok=True)) is not None
                ]
                if tiers and min(tiers)[0] <= 4:
                    scored.append((min(tiers), gz))
            if scored:
                best = min(s for s, _ in scored)
                hits = [gz for s, gz in scored if s == best]
                if len(hits) == 1:
                    gz_zone = hits[0]
        self.zone_cache[key] = gz_zone
        return gz_zone

    def match(self, region: str, zone: str, woreda: str) -> tuple[float, float] | None:
        gz_zone = self.resolve_zone(region, zone)
        hit = self.best_entry(region, gz_zone, woreda, 2) if gz_zone else None
        for name in [*zone.split(" - ")[1:], zone.split(" - ")[0]]:
            if hit is None:
                hit = self.best_entry(
                    region, gz_zone, SUBZONE_RE.sub("", name), 2, True
                )
        if hit is None and not gz_zone:
            hit = self.best_entry(region, gz_zone, woreda, 0)
        if hit is None:
            return None
        return float(hit["lat"]), float(hit["long"])

    def best_entry(
        self,
        region: str,
        gz_zone: str | None,
        name: str,
        max_cross_tier: int,
        short_ok: bool = False,
    ) -> dict | None:
        variants, is_town = nebe_variants(name)
        scored = []
        for e in self.by_region[region]:
            zone_mismatch = 0 if e["admin2_name"] == gz_zone else 1
            tiers = [
                (t, pen)
                for nf, pen in variants
                for gf in e["_forms"]
                if (t := pair_tier(nf, gf, short_ok or not zone_mismatch)) is not None
            ]
            if not tiers:
                continue
            tier, pen = min(tiers)
            if zone_mismatch and tier > max_cross_tier:
                continue
            town_mismatch = 0 if is_town == e["_town"] else 1
            cross_fuzzy = 1 if zone_mismatch and tier > 0 else 0
            scored.append(((town_mismatch, cross_fuzzy, tier, pen, zone_mismatch), e))
        if not scored:
            return None
        best = min(s for s, _ in scored)
        hits = [e for s, e in scored if s == best]
        return hits[0] if len(hits) == 1 else None
